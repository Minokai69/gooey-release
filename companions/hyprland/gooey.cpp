#include "gooey.hpp"
#include "barDeco.hpp"
#include <hyprland/src/Compositor.hpp>
#include <hyprland/src/desktop/state/WindowState.hpp>
#include <hyprland/src/desktop/state/FocusState.hpp>
#include <hyprland/src/state/MonitorState.hpp>
#include <hyprland/src/state/WorkspaceState.hpp>
#include <hyprland/src/config/shared/actions/ConfigActions.hpp>
#include <hyprland/src/config/shared/workspace/WorkspaceRuleManager.hpp>
#include <hyprland/src/config/lua/bindings/LuaBindingsInternal.hpp>
#include <hyprland/src/config/supplementary/executor/Executor.hpp>
#include <hyprland/src/managers/fullscreen/FullscreenController.hpp>
#include <hyprland/src/layout/space/Space.hpp>
#include <hyprland/src/layout/algorithm/Algorithm.hpp>
#include <hyprland/src/layout/algorithm/tiled/dwindle/DwindleAlgorithm.hpp>
#include <hyprland/src/layout/algorithm/tiled/scrolling/ScrollingAlgorithm.hpp>
#include <hyprland/src/debug/HyprCtl.hpp>
#include <charconv>
#include <sstream>
#include <filesystem>
#include <fstream>
#include <set>
#include <iomanip>
#include <cmath>

namespace {
namespace CA = Config::Actions;
std::string json(const std::string& s) { return "\"" + escapeJSONStrings(s) + "\""; }
std::string result(bool ok, const std::string& error = "") {
    return ok ? "{\"ok\":true}" : "{\"ok\":false,\"error\":" + json(error) + "}";
}
std::string result(const CA::ActionResult& r) { return result(r.has_value(), r ? "" : r.error().message); }
std::string trim(std::string s) {
    const auto start = s.find_first_not_of(" \t");
    return start == std::string::npos ? "" : s.substr(start, s.find_last_not_of(" \t") - start + 1);
}
bool unsignedID(const std::string& s, uint64_t& id) {
    auto [p, e] = std::from_chars(s.data(), s.data() + s.size(), id);
    return !s.empty() && e == std::errc{} && p == s.data() + s.size();
}
PHLWINDOW findWindow(const std::string& id) {
    uint64_t n;
    if (!unsignedID(id, n)) return nullptr;
    for (const auto& w : Desktop::windowState()->windows())
        if (validMapped(w) && w->m_stableID == n) return w;
    return nullptr;
}
bool onShelf(PHLWINDOW w) { return w && w->m_workspace && w->m_workspace->getConfigName() == "special:scratchpad"; }
Layout::ITiledAlgorithm* tiledAlgorithm(PHLWINDOW w) {
    return w && w->m_workspace && w->m_workspace->m_space && w->m_workspace->m_space->algorithm()
        ? w->m_workspace->m_space->algorithm()->tiledAlgo().get() : nullptr;
}
std::string layoutName(PHLWINDOW w) {
    const auto algorithm = tiledAlgorithm(w);
    if (dynamic_cast<Layout::Tiled::CDwindleAlgorithm*>(algorithm)) return "dwindle";
    if (dynamic_cast<Layout::Tiled::CScrollingAlgorithm*>(algorithm)) return "scrolling";
    return "other";
}
bool tileCanChange(PHLWINDOW w) {
    return w && !w->m_isFloating && !w->m_group &&
        Fullscreen::controller()->getFullscreenModes(w).internal == Fullscreen::FSMODE_NONE;
}
bool supportsSplit(PHLWINDOW w) {
    return tileCanChange(w) && dynamic_cast<Layout::Tiled::CDwindleAlgorithm*>(tiledAlgorithm(w));
}
struct ScrollingOwner {
    Layout::Tiled::CScrollingAlgorithm* algorithm = nullptr;
    SP<Layout::Tiled::SColumnData> column;
    SP<Layout::Tiled::SScrollingData> data;
};
std::optional<ScrollingOwner> scrollingOwner(PHLWINDOW w) {
    if (!w || w->m_isFloating || w->m_group) return std::nullopt;
    auto algorithm = dynamic_cast<Layout::Tiled::CScrollingAlgorithm*>(tiledAlgorithm(w));
    if (!algorithm) return std::nullopt;
    const auto target = algorithm->dataFor(w->layoutTarget());
    const auto column = target ? target->column.lock() : nullptr;
    const auto data = column ? column->scrollingData.lock() : nullptr;
    if (!column || !data || !data->controller || data->idx(column) < 0) return std::nullopt;
    return ScrollingOwner{algorithm, column, data};
}
bool columnCanChange(PHLWINDOW w, const std::optional<ScrollingOwner>& scrolling) {
    return tileCanChange(w) && scrolling && !scrolling->data->controller->getScrollInhibitor().isInhibited;
}
std::string scrollingState(const std::optional<ScrollingOwner>& scrolling) {
    if (!scrolling) return "null";
    const auto direction = scrolling->data->controller->getDirection();
    const char* directionName = direction == Layout::Tiled::SCROLL_DIR_LEFT ? "left" :
        direction == Layout::Tiled::SCROLL_DIR_UP ? "up" : direction == Layout::Tiled::SCROLL_DIR_DOWN ? "down" : "right";
    std::ostringstream out;
    out << std::boolalpha << "{\"columnWidth\":" << scrolling->column->getColumnWidth()
        << ",\"columnIndex\":" << scrolling->data->idx(scrolling->column)
        << ",\"columnCount\":" << scrolling->data->columns.size()
        << ",\"columnWindowCount\":" << scrolling->column->targetDatas.size()
        << ",\"direction\":" << json(directionName)
        << ",\"horizontal\":" << scrolling->data->controller->isPrimaryHorizontal()
        << ",\"viewportSize\":" << scrolling->algorithm->primaryViewportSize()
        << ",\"offset\":" << scrolling->algorithm->normalizedTapeOffset() << '}';
    return out.str();
}
PHLWORKSPACE regularOn(PHLMONITOR mon) {
    auto ws = mon ? mon->m_activeWorkspace : nullptr;
    return valid(ws) && !ws->m_isSpecialWorkspace ? ws : nullptr;
}
PHLWORKSPACE destination(const std::string& selector, bool create) {
    if (selector.empty() || selector.starts_with("special:") || (selector.find_first_of("\n\r;") != std::string::npos || selector.find('\0') != std::string::npos)) return nullptr;
    const bool named = selector.starts_with("name:") && selector.size() > 5;
    int64_t numeric = 0;
    const auto [p, ec] = std::from_chars(selector.data(), selector.data() + selector.size(), numeric);
    if (!named && (ec != std::errc{} || p != selector.data() + selector.size() || numeric == 0)) return nullptr;
    auto ws = named ? State::workspaceState()->query().name(selector.substr(5)).run() : State::workspaceState()->query().id(numeric).run();
    if (!ws && create && (named || numeric > 0))
        ws = Config::Lua::Bindings::Internal::resolveWorkspaceStr(selector);
    return valid(ws) && !ws->m_isSpecialWorkspace ? ws : nullptr;
}
PHLWORKSPACE scratchpad() { return Config::Lua::Bindings::Internal::resolveWorkspaceStr("special:scratchpad"); }
std::string shellQuote(const std::string& value) {
    std::string out = "'";
    for (char c : value) out += c == '\'' ? "'\\''" : std::string(1, c);
    return out + "'";
}
void openMenu(PHLWINDOW owner, const std::string& kind) {
    if (!validMapped(owner)) return;
    const auto explicitPath = std::getenv("GOOEY_SHELL_PATH");
    const auto omarchy = std::getenv("OMARCHY_PATH");
    const std::string path = explicitPath ? explicitPath : (omarchy ? std::string(omarchy) + "/shell" : "/usr/share/omarchy/shell");
    // All dynamic data is quoted. Only a validated native ID and fixed menu enum leave the compositor.
    Config::Supplementary::executor()->spawn("qs ipc -p " + shellQuote(path) +
        " call gooey.window-tools openMenuForInstance " + std::to_string(owner->m_stableID) + " " + kind + " " + shellQuote(g_pCompositor->m_instanceSignature));
}
// Origin data is recovery assistance only; live scratchpad membership always wins.
std::map<uint64_t, std::pair<std::string, std::string>> origins;
std::filesystem::path originPath() {
    const auto runtime = std::getenv("XDG_RUNTIME_DIR");
    if (!runtime) return {};
    return std::filesystem::path(runtime) / ("gooey-shelf-" + g_pCompositor->m_instanceSignature + ".txt");
}
void persistOrigins() {
    const auto path = originPath();
    if (path.empty()) return;
    auto tmp = path; tmp += ".tmp";
    std::ofstream f(tmp, std::ios::trunc);
    for (const auto& [id, origin] : origins) f << id << ' ' << std::quoted(origin.first) << ' ' << std::quoted(origin.second) << '\n';
    f.close();
    if (!f.fail()) { std::error_code e; std::filesystem::rename(tmp, path, e); }
}
std::string action(PHLWINDOW w, const std::string& name, const std::string& args) {
    if (!validMapped(w)) return result(false, "Window no longer exists");
    if (name == "tile-narrower" || name == "tile-wider" || name == "tile-shorter" || name == "tile-taller") {
        if (!supportsSplit(w)) return result(false, "Tile sizing requires a dwindle tile");
        return action(w, "resize", name == "tile-narrower" ? "-200 0" : name == "tile-wider" ? "200 0" : name == "tile-shorter" ? "0 -200" : "0 200");
    }
    if (name == "column-quarter" || name == "column-half" || name == "column-85" || name == "column-full")
        return action(w, "column-width", name == "column-quarter" ? "quarter" : name == "column-half" ? "half" : name == "column-85" ? "85" : "full");
    if (name == "close") return result(CA::closeWindow(w));
    if (name == "focus") return result(CA::focus(w));
    if (name == "menu-workspace" || name == "menu-actions" || name == "menu-layout") {
        bool anchored = false;
        for (const auto& bar : g_pGlobalState->bars) {
            if (bar && bar->getOwner() == w) {
                const auto anchor = bar->menuAnchor();
                anchored = bar->decorationVisible() && anchor.w > 0 && anchor.h > 0;
                break;
            }
        }
        if (!anchored) return result(false, "This window has no visible attached controls");
        openMenu(w, name == "menu-workspace" ? "workspace" : name == "menu-layout" ? "layout" : "actions");
        return result(true);
    }
    if (w->m_group) return result(false, "Ungroup this window before using this action; other group members will not be moved");
    if (name == "float") return result(CA::floatWindow(CA::TOGGLE_ACTION_TOGGLE, w));
    if (name == "fullscreen") {
        const auto mode = Fullscreen::controller()->isFullscreen(w, Fullscreen::FSMODE_FULLSCREEN) ? Fullscreen::FSMODE_NONE : Fullscreen::FSMODE_FULLSCREEN;
        return result(CA::fullscreenWindow(mode, true, w));
    }
    if (name == "maximize") {
        auto mode = Fullscreen::controller()->isFullscreen(w, Fullscreen::FSMODE_MAXIMIZED) ? Fullscreen::FSMODE_NONE : Fullscreen::FSMODE_MAXIMIZED;
        return result(CA::fullscreenWindow(mode, true, w));
    }
    if (name == "shelf") {
        if (!onShelf(w)) {
            if (!w->m_workspace || w->m_workspace->m_isSpecialWorkspace) return result(false, "Send to Shelf from a normal workspace");
            auto target = scratchpad();
            if (!valid(target)) return result(false, "Scratchpad unavailable");
            auto mon = w->m_monitor.lock();
            origins[w->m_stableID] = {w->m_workspace->getConfigName(), mon ? mon->m_name : ""};
            persistOrigins();
            const auto r = CA::moveToWorkspace(target, true, w);
            if (!r) { origins.erase(w->m_stableID); persistOrigins(); }
            return result(r);
        }
        auto target = args.empty() ? regularOn(w->m_monitor.lock()) : destination(args, false);
        if (!target) target = regularOn(w->m_monitor.lock());
        if (!target) target = regularOn(Desktop::focusState()->monitor());
        if (!target) for (const auto& mon : State::monitorState()->monitors()) if ((target = regularOn(mon))) break;
        if (!target) return result(false, "Choose an available normal workspace; window remains on Shelf");
        const auto r = CA::moveToWorkspace(target, true, w);
        if (r) { origins.erase(w->m_stableID); persistOrigins(); }
        return result(r);
    }
    if (name == "workspace") {
        std::istringstream in(args); std::string follow, dest;
        in >> follow; std::getline(in, dest); dest = trim(dest);
        if (follow != "0" && follow != "1") return result(false, "Expected follow 0 or 1");
        auto target = destination(dest, true);
        if (!target) return result(false, "Invalid normal workspace destination");
        if (target == w->m_workspace) return result(true);
        const auto r = CA::moveToWorkspace(target, follow == "0", w);
        if (r) { origins.erase(w->m_stableID); persistOrigins(); }
        return result(r);
    }
    if (name == "swap") {
        auto dir = args == "l" ? Math::DIRECTION_LEFT : args == "r" ? Math::DIRECTION_RIGHT : args == "u" ? Math::DIRECTION_UP : args == "d" ? Math::DIRECTION_DOWN : Math::DIRECTION_DEFAULT;
        if (dir == Math::DIRECTION_DEFAULT || !supportsSplit(w)) return result(false, "Swap tiles requires a dwindle tile and direction");
        return result(CA::swapInDirection(dir, w));
    }
    if (name == "resize") {
        std::istringstream in(args); int x, y; std::string extra;
        if (!(in >> x >> y) || (in >> extra) || x < -400 || x > 400 || y < -400 || y > 400)
            return result(false, "Expected width/height increments between -400 and 400");
        return result(CA::resize(Vector2D{x, y}, true, w));
    }
    if (name == "column-width" || name == "column-center" || name == "column-focus") {
        const auto scrolling = scrollingOwner(w);
        if (!scrolling || !columnCanChange(w, scrolling))
            return result(false, "Column controls require an unmaximized scrolling tile");
        if (name == "column-width") {
            const float width = args == "quarter" ? 0.25F : args == "half" ? 0.5F : args == "85" ? 0.85F : args == "full" ? 1.F :
                args == "third" ? 1.F / 3.F : args == "two-thirds" ? 2.F / 3.F : 0.F;
            if (width == 0) return result(false, "Choose quarter, half, 85, full, third, or two-thirds column width");
            // Same operation as Hyprland's colresize, on the explicitly selected
            // owner's column. Native scrolling owns sizes, gaps and viewport.
            scrolling->column->setColumnWidth(width);
            scrolling->data->centerOrFitCol(scrolling->column);
            scrolling->data->recalculate();
            return result(true);
        }
        if (name == "column-center") {
            if (!args.empty()) return result(false, "Center column does not take arguments");
            scrolling->data->centerCol(scrolling->column);
            scrolling->data->recalculate();
            return result(true);
        }
        if (args != "previous" && args != "next") return result(false, "Choose previous or next column");
        const auto column = args == "previous" ? scrolling->data->prev(scrolling->column) : scrolling->data->next(scrolling->column);
        if (!column) return result(false, "No column in that direction");
        // Explicitly fit/center as native focus-following can be disabled. The
        // compositor selects the destination column's last focused member.
        scrolling->data->centerOrFitCol(column);
        scrolling->data->recalculate();
        scrolling->algorithm->focusColumn(column);
        return result(true);
    }
    if (name == "split") {
        if (!supportsSplit(w)) return result(false, "Change split requires a dwindle tile");
        // One synchronous compositor callback; no subprocess/focus race.
        auto focused = CA::focus(w);
        if (!focused || Desktop::focusState()->window() != w) return result(false, "Unable to focus selected window");
        return result(CA::layoutMessage("togglesplit"));
    }
    return result(false, "Unknown Gooey action");
}
std::string windowRequest(std::string text) {
    text = trim(text);
    if (text.starts_with("gooey:window")) text = trim(text.substr(14));
    std::istringstream in(text); std::string flag, instance, name, id, args;
    in >> flag >> instance >> name >> id; std::getline(in, args);
    if (flag != "--instance" || instance != g_pCompositor->m_instanceSignature)
        return result(false, "Compositor instance changed; refresh the window list");
    return action(findWindow(id), name, trim(args));
}
std::string shelfRequest() {
    auto ws = scratchpad();
    return valid(ws) ? result(CA::toggleSpecial(ws)) : result(false, "Scratchpad unavailable");
}
std::optional<std::string> decodeFontFamily(const std::string& hex) {
    if (hex.empty() || hex.size() > 1024 || hex.size() % 2) return std::nullopt;
    std::string family;
    for (size_t i = 0; i < hex.size(); i += 2) {
        unsigned int byte = 0;
        const auto [end, error] = std::from_chars(hex.data() + i, hex.data() + i + 2, byte, 16);
        if (error != std::errc{} || end != hex.data() + i + 2) return std::nullopt;
        family.push_back(static_cast<char>(byte));
    }
    // Validate UTF-8, excluding controls, overlong forms, and surrogate values.
    for (size_t i = 0; i < family.size();) {
        const auto first = static_cast<unsigned char>(family[i++]);
        uint32_t code = first;
        int trailing = 0;
        uint32_t minimum = 0;
        if (first >= 0xf0 && first <= 0xf4) { code = first & 7; trailing = 3; minimum = 0x10000; }
        else if (first >= 0xe0 && first <= 0xef) { code = first & 15; trailing = 2; minimum = 0x800; }
        else if (first >= 0xc2 && first <= 0xdf) { code = first & 31; trailing = 1; minimum = 0x80; }
        else if (first >= 0x80) return std::nullopt;
        while (trailing--) {
            if (i >= family.size()) return std::nullopt;
            const auto next = static_cast<unsigned char>(family[i++]);
            if ((next & 0xc0) != 0x80) return std::nullopt;
            code = (code << 6) | (next & 0x3f);
        }
        if (code < minimum || code > 0x10ffff || (code >= 0xd800 && code <= 0xdfff) || code < 0x20 || code == 0x7f)
            return std::nullopt;
    }
    if (trim(family).empty()) return std::nullopt;
    return family;
}
std::string themeRequest(std::string text) {
    text = trim(text);
    if (text.starts_with("gooey:theme")) text = trim(text.substr(13));
    std::istringstream in(text);
    std::string flag, instance, key, value;
    in >> flag >> instance;
    if (flag != "--instance" || instance != g_pCompositor->m_instanceSignature)
        return result(false, "Compositor instance changed; refresh the theme");
    auto next = g_pGlobalState->theme;
    const std::map<std::string, CHyprColor*> colors{
        {"background", &next.background}, {"foreground", &next.foreground}, {"accent", &next.accent},
        {"muted", &next.muted}, {"danger", &next.danger}, {"border", &next.border}, {"normal", &next.normal},
        {"hover", &next.hover}, {"pressed", &next.pressed}, {"normalBorder", &next.normalBorder}, {"hoverBorder", &next.hoverBorder}};
    const std::map<std::string, double*> numbers{{"normalBorderWidth", &next.normalBorderWidth},
        {"hoverBorderWidth", &next.hoverBorderWidth}, {"radius", &next.radius}, {"scale", &next.scale}, {"height", &next.height}, {"fontSize", &next.fontSize}};
    std::set<std::string> seen;
    while (in >> key) {
        if (!(in >> value) || !seen.insert(key).second) return result(false, "Incomplete or duplicate theme field");
        if (const auto field = colors.find(key); field != colors.end()) {
            uint32_t color;
            const auto [end, error] = std::from_chars(value.data(), value.data() + value.size(), color, 16);
            if (value.size() != 8 || error != std::errc{} || end != value.data() + value.size())
                return result(false, "Expected eight-digit ARGB theme color");
            *field->second = CHyprColor{static_cast<uint64_t>(color)};
        } else if (const auto field = numbers.find(key); field != numbers.end()) {
            double number;
            const auto [end, error] = std::from_chars(value.data(), value.data() + value.size(), number);
            if (error != std::errc{} || end != value.data() + value.size() || !std::isfinite(number))
                return result(false, "Expected finite theme dimension");
            *field->second = number;
        } else if (key == "fontFamilyHex") {
            const auto family = decodeFontFamily(value);
            if (!family) return result(false, "Expected a nonempty UTF-8 font family encoded as hex");
            next.fontFamily = *family;
        } else return result(false, "Unknown theme field");
    }
    if (seen.size() != colors.size() + numbers.size() + 1 || next.radius < 0 || next.radius > 256 ||
        next.scale < .01 || next.scale > 16 || next.height < 1 || next.height > 512 || next.fontSize < 1 || next.fontSize > 512 ||
        next.normalBorderWidth < 0 || next.normalBorderWidth > 32 || next.hoverBorderWidth < 0 || next.hoverBorderWidth > 32)
        return result(false, "Theme fields missing or outside supported dimensions");
    // Damage the old compact bounds before a size change, then the new ones.
    for (auto& bar : g_pGlobalState->bars) if (bar) bar->damageEntire();
    next.ready = true;
    next.revision++;
    g_pGlobalState->theme = next;
    for (auto& button : g_pGlobalState->buttons) {
        button.fgcol = next.foreground;
        button.bgcol = next.normal;
    }
    for (auto& bar : g_pGlobalState->bars) if (bar) bar->onConfigReloaded();
    return result(true);
}
std::string themeState() {
    const auto& theme = g_pGlobalState->theme;
    const auto color = [](const CHyprColor& value) { return json(std::format("{:08x}", static_cast<uint32_t>(value.getAsHex()))); };
    std::ostringstream out;
    out << std::boolalpha << "{\"ready\":" << theme.ready << ",\"revision\":" << theme.revision
        << ",\"background\":" << color(theme.background) << ",\"foreground\":" << color(theme.foreground)
        << ",\"accent\":" << color(theme.accent) << ",\"muted\":" << color(theme.muted) << ",\"danger\":" << color(theme.danger)
        << ",\"border\":" << color(theme.border) << ",\"normal\":" << color(theme.normal) << ",\"hover\":" << color(theme.hover)
        << ",\"pressed\":" << color(theme.pressed) << ",\"normalBorder\":" << color(theme.normalBorder)
        << ",\"hoverBorder\":" << color(theme.hoverBorder) << ",\"normalBorderWidth\":" << theme.normalBorderWidth
        << ",\"hoverBorderWidth\":" << theme.hoverBorderWidth << ",\"radius\":" << theme.radius
        << ",\"scale\":" << theme.scale << ",\"height\":" << theme.height
        << ",\"fontSize\":" << theme.fontSize << ",\"fontFamily\":" << json(theme.fontFamily) << '}';
    return out.str();
}
std::string stateRequest() {
    std::ostringstream out; out << std::boolalpha;
    out << "{\"protocolVersion\":1,\"instance\":" << json(g_pCompositor->m_instanceSignature)
        << ",\"decorationMode\":\"integrated-frame\",\"reservedTop\":" << g_pGlobalState->theme.height << ",\"theme\":" << themeState()
        << ",\"toolbarHeight\":" << g_pGlobalState->theme.height << ",\"windows\":[";
    bool comma = false;
    std::set<uint64_t> shelfIDs;
    for (const auto& w : Desktop::windowState()->windows()) {
        if (!validMapped(w) || w->isX11OverrideRedirect()) continue;
        auto ws = w->m_workspace; auto mon = w->m_monitor.lock();
        auto box = w->geometricBox(Desktop::View::IGeometric::GEOMETRIC_CURRENT);
        CBox anchor;
        bool decorationVisible = false, controlsShown = false;
        double reservedTop = 0;
        std::string appName;
        std::string buttons = "[]", hovered;
        for (const auto& bar : g_pGlobalState->bars) if (bar && bar->getOwner() == w) {
            anchor = bar->menuAnchor();
            decorationVisible = bar->decorationVisible() && anchor.w > 0 && anchor.h > 0;
            buttons = bar->buttonState();
            hovered = bar->hoverAction();
            controlsShown = bar->controlsShown();
            reservedTop = bar->reservedHeight();
            appName = bar->appName();
            break;
        }
        const bool grouped = bool(w->m_group), shelved = onShelf(w);
        const auto scrolling = scrollingOwner(w);
        const bool columnControls = columnCanChange(w, scrolling);
        const auto resizeAxes = gooeyResizeAxes(w);
        if (shelved) shelfIDs.insert(w->m_stableID);
        if (comma) out << ','; comma = true;
        out << "{\"id\":" << json(std::to_string(w->m_stableID)) << ",\"address\":" << json(std::format("0x{:x}", (uintptr_t)w.get()))
            << ",\"title\":" << json(w->m_title) << ",\"appId\":" << json(w->m_class)
            << ",\"workspaceId\":" << (ws ? ws->m_id : 0) << ",\"workspaceName\":" << json(ws ? ws->getConfigName() : "")
            << ",\"monitor\":" << json(mon ? mon->m_name : "") << ",\"floating\":" << w->m_isFloating << ",\"shelved\":" << shelved
            << ",\"grouped\":" << grouped << ",\"focused\":" << (Desktop::focusState()->window() == w)
            << ",\"hoverAction\":" << json(hovered) << ",\"hoverText\":" << json(gooeyButtonDescription(w, hovered))
            << ",\"layout\":" << json(layoutName(w)) << ",\"scrolling\":" << scrollingState(scrolling)
            << ",\"fullscreen\":" << (int)Fullscreen::controller()->getFullscreenModes(w).internal
            << ",\"maximized\":" << Fullscreen::controller()->isFullscreen(w, Fullscreen::FSMODE_MAXIMIZED)
            << ",\"x\":" << box.x << ",\"y\":" << box.y << ",\"width\":" << box.w << ",\"height\":" << box.h
            << ",\"anchor\":{\"x\":" << anchor.x << ",\"y\":" << anchor.y << ",\"width\":" << anchor.w << ",\"height\":" << anchor.h << '}'
            << ",\"decorationVisible\":" << decorationVisible << ",\"controlsShown\":" << controlsShown
            << ",\"reservedTop\":" << reservedTop << ",\"appName\":" << json(appName) << ",\"buttons\":" << buttons
            << ",\"restoreWorkspaceId\":" << (regularOn(mon) ? regularOn(mon)->m_id : 0)
            << ",\"capabilities\":{\"close\":true,\"focus\":true,\"shelf\":" << (!grouped && (!ws || !ws->m_isSpecialWorkspace || shelved))
            << ",\"float\":" << !grouped << ",\"maximize\":" << !grouped << ",\"workspace\":" << !grouped
            << ",\"swap\":" << supportsSplit(w) << ",\"resize\":" << !grouped << ",\"split\":" << supportsSplit(w)
            << ",\"resizeHorizontal\":" << resizeAxes.horizontal << ",\"resizeVertical\":" << resizeAxes.vertical
            << ",\"columnWidth\":" << columnControls << ",\"columnCenter\":" << columnControls
            << ",\"columnPrevious\":" << (columnControls && bool(scrolling->data->prev(scrolling->column)))
            << ",\"columnNext\":" << (columnControls && bool(scrolling->data->next(scrolling->column))) << "}}";
    }
    bool pruned = false;
    for (auto it = origins.begin(); it != origins.end();) { if (!shelfIDs.contains(it->first)) { it = origins.erase(it); pruned = true; } else ++it; }
    if (pruned) persistOrigins();
    out << "],\"workspaces\":["; comma = false;
    for (const auto& weak : State::workspaceState()->workspaces()) {
        auto ws = weak.lock();
        if (!valid(ws) || ws->m_isSpecialWorkspace) continue;
        if (comma) out << ','; comma = true;
        auto mon = ws->m_monitor.lock();
        out << "{\"id\":" << ws->m_id << ",\"name\":" << json(ws->m_name) << ",\"selector\":" << json(ws->getConfigName()) << ",\"monitor\":" << json(mon ? mon->m_name : "") << ",\"special\":false}";
    }
    out << "],\"configuredWorkspaces\":["; comma = false;
    for (const auto& rule : Config::workspaceRuleMgr()->getAllWorkspaceRules()) {
        if (!rule->isEnabled()) continue;
        auto name = rule->m_workspaceString;
        int64_t n = 0; const auto [p, e] = std::from_chars(name.data(), name.data()+name.size(), n);
        if (!name.starts_with("name:") && !(e == std::errc{} && p == name.data()+name.size() && n > 0)) continue;
        if (comma) out << ','; comma = true;
        out << "{\"selector\":" << json(name) << ",\"name\":" << json(rule->m_workspaceName.empty() ? name : rule->m_workspaceName) << '}';
    }
    out << "],\"monitors\":["; comma = false;
    for (const auto& mon : State::monitorState()->monitors()) {
        if (comma) out << ','; comma = true;
        auto ws = regularOn(mon);
        out << "{\"name\":" << json(mon->m_name) << ",\"activeWorkspaceId\":" << (ws ? ws->m_id : 0) << ",\"activeWorkspaceName\":" << json(ws ? ws->m_name : "")
            << ",\"x\":" << mon->m_position.x << ",\"y\":" << mon->m_position.y << ",\"width\":" << mon->m_size.x << ",\"height\":" << mon->m_size.y
            << ",\"scale\":" << mon->m_scale << '}';
    }
    return out.str() + "]}";
}
}
void gooeyDefaultButtons() {
    g_pGlobalState->buttons.clear();
    // Window operations live in Quickshell popups. The full-width strip keeps
    // native move/resize grabs and menu openers directly attached to the owner.
    for (const auto& action : {"drag-grip", "menu-actions", "resize-grip"}) {
        g_pGlobalState->buttons.push_back({action, true, g_pGlobalState->theme.foreground, g_pGlobalState->theme.normal, 32, ""});
    }
}
std::string gooeyButtonLabel(PHLWINDOW w, const std::string& name) {
    if (name == "close") return "×";
    if (name == "menu-actions") return "≡";
    if (name == "float") return w && w->m_isFloating ? "▦" : "□";
    if (name == "menu-workspace") return "W";
    if (name == "shelf") return onShelf(w) ? "↑" : "↓";
    return "↘";
}
void gooeyButtonAction(PHLWINDOW w, const std::string& name, const std::string& args) {
    const auto response = action(w, name, args);
    if (response != result(true)) {
        HyprlandAPI::addNotification(PHANDLE, "Gooey: " + response, CHyprColor(0xffe0af68), 4000);
    }
}
void gooeyRegister() {
    // Direct HyprCtl commands avoid the Lua-vs-legacy dispatcher grammar entirely.
    HyprlandAPI::registerHyprCtlCommand(PHANDLE, {"gooey:state", true, [](auto, auto) { return stateRequest(); }});
    HyprlandAPI::registerHyprCtlCommand(PHANDLE, {"dispatch gooey:state", true, [](auto, auto) { return stateRequest(); }});
    HyprlandAPI::registerHyprCtlCommand(PHANDLE, {"gooey:shelf", true, [](auto, auto) { return shelfRequest(); }});
    HyprlandAPI::registerHyprCtlCommand(PHANDLE, {"dispatch gooey:shelf", true, [](auto, auto) { return shelfRequest(); }});
    HyprlandAPI::registerHyprCtlCommand(PHANDLE, {"gooey:window", false, [](auto, auto request) { return windowRequest(request); }});
    HyprlandAPI::registerHyprCtlCommand(PHANDLE, {"gooey:theme", false, [](auto, auto request) { return themeRequest(request); }});
    HyprlandAPI::addDispatcherV2(PHANDLE, "gooey:window", [](auto request) {
        const auto r = windowRequest(request); return SDispatchResult{.success = r == result(true), .error = r};
    });
    std::ifstream f(originPath()); uint64_t id; std::string workspace, monitor;
    while (f >> id >> std::quoted(workspace) >> std::quoted(monitor)) origins[id] = {workspace, monitor};
}

std::string gooeyRestoreDestination(PHLWINDOW w) {
    auto ws = w && onShelf(w) ? regularOn(w->m_monitor.lock()) : nullptr;
    return ws ? ws->getConfigName() : "";
}

std::string gooeyButtonDescription(PHLWINDOW w, const std::string& name) {
    if (name == "tile-narrower") return "Make this tile narrower";
    if (name == "tile-wider") return "Make this tile wider";
    if (name == "tile-shorter") return "Make this tile shorter";
    if (name == "tile-taller") return "Make this tile taller";
    if (name.starts_with("column-")) {
        const auto scrolling = scrollingOwner(w);
        const std::string dimension = scrolling && !scrolling->data->controller->isPrimaryHorizontal() ? "height" : "width";
        return "Set column " + dimension + " to " + (name == "column-quarter" ? "25%" : name == "column-half" ? "50%" : name == "column-85" ? "85%" : "100%");
    }
    if (name == "fullscreen") return "Full screen (Super+F); press Super+F to restore";
    if (name == "close") return "Close window";
    if (name == "menu-actions") return "Tiling controls and window actions";
    if (name == "float") return w && w->m_isFloating ? "Tile window" : "Float window";
    if (name == "menu-workspace") return "Send to workspace";
    if (name == "shelf") return onShelf(w) ? "Take off shelf" : "Send to shelf";
    if (name == "resize-grip") return "Click for size controls; hold and drag to resize";
    if (name == "drag-grip") return "Hold and drag to move";
    return "";
}

std::string gooeyTileLayout(PHLWINDOW owner) {
    if (!validMapped(owner)) return "";
    if (supportsSplit(owner)) return "dwindle";
    if (columnCanChange(owner, scrollingOwner(owner))) return "scrolling";
    return "";
}

GooeyResizeAxes gooeyResizeAxes(PHLWINDOW owner) {
    if (!validMapped(owner) || owner->m_group ||
        Fullscreen::controller()->getFullscreenModes(owner).internal != Fullscreen::FSMODE_NONE) return {};
    if (owner->m_isFloating) return {true, true};
    if (auto dwindle = dynamic_cast<Layout::Tiled::CDwindleAlgorithm*>(tiledAlgorithm(owner))) {
        GooeyResizeAxes axes;
        auto node = dwindle->getNodeFromWindow(owner);
        // Ancestor splits, including outer splits, determine which dimensions can change.
        while (node) {
            auto parent = node->pParent.lock();
            if (!parent) break;
            const auto first = parent->children[0].lock();
            const auto second = parent->children[1].lock();
            if (first && second && first->valid && second->valid) {
                axes.horizontal |= std::abs(first->box.x - second->box.x) > 1;
                axes.vertical |= std::abs(first->box.y - second->box.y) > 1;
            }
            node = parent;
        }
        return axes;
    }
    const auto scrolling = scrollingOwner(owner);
    if (columnCanChange(owner, scrolling)) {
        const auto direction = scrolling->data->controller->getDirection();
        const bool horizontal = direction == Layout::Tiled::SCROLL_DIR_RIGHT || direction == Layout::Tiled::SCROLL_DIR_LEFT;
        const bool stacked = scrolling->column->targetDatas.size() > 1;
        return horizontal ? GooeyResizeAxes{true, stacked} : GooeyResizeAxes{stacked, true};
    }
    return {};
}
