#include "barDeco.hpp"

#include <hyprland/src/Compositor.hpp>
#include <hyprland/src/desktop/state/FocusState.hpp>
#include <hyprland/src/desktop/state/WindowState.hpp>
#include <hyprland/src/desktop/state/LayerState.hpp>
#include <hyprland/src/desktop/state/ViewHitTester.hpp>
#include <hyprland/src/desktop/view/Window.hpp>
#include <hyprland/src/desktop/view/LayerSurface.hpp>
#include <hyprland/src/helpers/MiscFunctions.hpp>
#include <hyprland/src/managers/SeatManager.hpp>
#include <hyprland/src/managers/EventManager.hpp>
#include <hyprland/src/managers/fullscreen/FullscreenController.hpp>
#include <hyprland/src/managers/input/InputManager.hpp>
#include <hyprland/src/render/Renderer.hpp>
#include <hyprland/src/config/ConfigManager.hpp>
#include <hyprland/src/config/shared/animation/AnimationTree.hpp>
#include <hyprland/src/config/shared/parserUtils/ParserUtils.hpp>
#include <hyprland/src/config/supplementary/executor/Executor.hpp>
#include <hyprland/src/config/shared/actions/ConfigActions.hpp>
#include <hyprland/src/animation/AnimationManager.hpp>
#include <hyprland/src/protocols/LayerShell.hpp>
#include <hyprland/src/event/EventBus.hpp>
#include <hyprland/src/layout/LayoutManager.hpp>
#include <hyprland/src/render/OpenGL.hpp>
#include <hyprland/src/state/MonitorState.hpp>

#include "globals.hpp"
#include "gooey.hpp"
#include "BarPassElement.hpp"
#include "appIdentity.hpp"

#include <array>
#include <climits>
#include <cmath>
#include <cairo/cairo.h>
#include <pango/pangocairo.h>
#include <hyprgraphics/cairo/CairoSurface.hpp>
#include <drm_fourcc.h>

using namespace Render::GL;

static CHyprColor configColor(Config::INTEGER color) {
    return CHyprColor{static_cast<uint64_t>(color)};
}

namespace {
double tabHeight() {
    return g_pGlobalState->theme.ready ? g_pGlobalState->theme.height : g_pGlobalState->config.barHeight->value();
}
struct TabControl { const char* action; double x; double width; };
double titleGroupWidth(PHLWINDOW owner, double available, double height) {
    const auto& theme = g_pGlobalState->theme;
    const auto name = owner ? OMousey::windowAppName(owner->m_class, owner->m_title) : "Window";
    const auto family = theme.ready ? theme.fontFamily : g_pGlobalState->config.barTextFont->value();
    const double size = theme.ready ? theme.fontSize : g_pGlobalState->config.barTextSize->value();
    // Measure on the CPU so drawing and pointer hit testing share stable geometry.
    static std::string previous;
    static double width = 0;
    const auto key = std::format("{}:{}:{}", name, family, size);
    if (key != previous) {
        Hyprgraphics::CCairoSurface surface{cairo_image_surface_create(CAIRO_FORMAT_ARGB32, 1, 1)};
        const auto cr = std::unique_ptr<cairo_t, decltype(&cairo_destroy)>{cairo_create(surface.cairo()), cairo_destroy};
        // Match the shaping/font fallback used by Hyprland's text renderer.
        // One extra logical pixel covers font-size rounding on fractional outputs.
        auto* layout = pango_cairo_create_layout(cr.get());
        auto* font = pango_font_description_new();
        pango_font_description_set_family(font, family.c_str());
        pango_font_description_set_absolute_size(font, (std::ceil(size) + 1) * PANGO_SCALE);
        pango_layout_set_font_description(layout, font);
        pango_layout_set_text(layout, name.c_str(), -1);
        PangoRectangle ink{}, logical{};
        pango_layout_get_pixel_extents(layout, &ink, &logical);
        width = std::max(logical.width, ink.x + ink.width) + 2;
        pango_font_description_free(font);
        g_object_unref(layout);
        previous = key;
    }
    return std::clamp(width + 1.5 * height, height, std::max(height, available));
}
std::array<TabControl, 12> tabControls(const CBox& box, PHLWINDOW owner) {
    if (box.h <= 0 || box.w < box.h) return {};
    if (box.w < 3 * box.h) return {{{"menu-actions", 0, box.w}}};
    std::vector<const char*> left;
    const bool compact = box.w < 8 * box.h;
    const auto layout = gooeyTileLayout(owner);
    if (box.w >= 14 * box.h) {
        if (layout == "dwindle") {
            const auto axes = gooeyResizeAxes(owner);
            if (axes.horizontal) left.insert(left.end(), {"tile-narrower", "tile-wider"});
            if (axes.vertical) left.insert(left.end(), {"tile-shorter", "tile-taller"});
        }
        if (layout == "scrolling") left.insert(left.end(), {"column-quarter", "column-half", "column-85", "column-full"});
    }
    const double start = left.size() * box.h;
    const double end = box.w - (compact ? 1 : 5) * box.h;
    const double available = std::max(box.h, box.w - 2 * std::max(start, box.w - end));
    const double group = titleGroupWidth(owner, available, box.h);
    const double center = std::clamp(box.w / 2, start + group / 2, end - group / 2);
    const double resizeX = center + group / 2 - box.h;
    std::array<TabControl, 12> controls{};
    controls[0] = {"drag-grip", start, resizeX - start};
    controls[1] = {"resize-grip", resizeX, box.h};
    controls[2] = {"drag-grip", resizeX + box.h, end - resizeX - box.h};
    size_t index = 3;
    for (size_t i = 0; i < left.size(); ++i) controls[index++] = {left[i], i * box.h, box.h};
    if (compact) controls[index++] = {"menu-actions", end, box.h};
    else {
        const std::array<const char*, 5> right = {"menu-actions", "shelf", "menu-workspace", "fullscreen", "close"};
        for (size_t i = 0; i < right.size(); ++i)
            controls[index++] = {right[i], end + i * box.h, box.h};
    }
    return controls;
}
}

// One logical 24px grid keeps every symbol consistent and independent of fonts.
// Cache antialiased strokes at the output scale, then composite one texture per icon.
static SP<Render::ITexture> makeActionIcon(const std::string& action, bool floating, bool shelved, float scale, CHyprColor color) {
    const int extent = std::max(1, static_cast<int>(std::ceil(24 * scale)));
    Hyprgraphics::CCairoSurface surface{cairo_image_surface_create(CAIRO_FORMAT_ARGB32, extent, extent)};
    if (surface.status() != CAIRO_STATUS_SUCCESS) return {};
    const auto cr = std::unique_ptr<cairo_t, decltype(&cairo_destroy)>{cairo_create(surface.cairo()), cairo_destroy};
    cairo_scale(cr.get(), extent / 24., extent / 24.);
    cairo_set_source_rgba(cr.get(), color.r, color.g, color.b, color.a);
    cairo_set_line_width(cr.get(), 1.8);
    cairo_set_line_cap(cr.get(), CAIRO_LINE_CAP_ROUND);
    cairo_set_line_join(cr.get(), CAIRO_LINE_JOIN_ROUND);
    const auto line = [&](double x1, double y1, double x2, double y2) {
        cairo_move_to(cr.get(), x1, y1);
        cairo_line_to(cr.get(), x2, y2);
    };
    const auto frame = [&](double x, double y, double w, double h) {
        cairo_rectangle(cr.get(), x, y, w, h);
    };
    if (action == "close") {
        line(6, 6, 18, 18); line(6, 18, 18, 6);
    } else if (action == "menu-actions") {
        for (const auto x : {5., 12., 19.}) {
            cairo_arc(cr.get(), x, 12, 1.5, 0, 2 * M_PI);
            cairo_fill(cr.get());
        }
    } else if (action == "drag-grip") {
        for (const auto x : {8., 16.}) for (const auto y : {5., 12., 19.}) {
            cairo_arc(cr.get(), x, y, 1.25, 0, 2 * M_PI);
            cairo_fill(cr.get());
        }
    } else if (action == "float") {
        if (floating) {
            frame(4, 5, 16, 14); line(12, 5, 12, 19);
        } else {
            // Overlapping windows: lifting a tile into the floating layer.
            line(4, 15, 4, 5); line(4, 5, 15, 5);
            frame(8, 9, 12, 10);
        }
    } else if (action == "menu-workspace") {
        frame(4, 4, 6, 6); frame(14, 4, 6, 6);
        frame(4, 14, 6, 6); frame(14, 14, 6, 6);
    } else if (action == "shelf") {
        line(4, 15, 4, 20); line(4, 20, 20, 20); line(20, 20, 20, 15);
        if (shelved) {
            line(12, 15, 12, 4); line(7.5, 8.5, 12, 4); line(12, 4, 16.5, 8.5);
        } else {
            line(12, 4, 12, 15); line(7.5, 10.5, 12, 15); line(12, 15, 16.5, 10.5);
        }
    } else if (action.starts_with("tile-")) {
        const bool vertical = action == "tile-shorter" || action == "tile-taller";
        const bool outward = action == "tile-wider" || action == "tile-taller";
        if (vertical) { cairo_translate(cr.get(), 24, 0); cairo_rotate(cr.get(), M_PI / 2); }
        line(4, 7, 4, 17); line(20, 7, 20, 17);
        line(7, 12, 17, 12);
        const double l = outward ? 6 : 10, r = outward ? 18 : 14;
        const double d = outward ? 3 : -3;
        line(l, 12, l+d, 9); line(l, 12, l+d, 15);
        line(r, 12, r-d, 9); line(r, 12, r-d, 15);
    } else if (action.starts_with("column-")) {
        frame(3, 5, 18, 14);
        cairo_stroke(cr.get());
        const double fraction = action == "column-quarter" ? .25 : action == "column-half" ? .5 : action == "column-85" ? .85 : 1.;
        cairo_rectangle(cr.get(), 6, 8, 12 * fraction, 8);
        cairo_fill(cr.get());
    } else if (action == "fullscreen") {
        line(5, 10, 5, 5); line(5, 5, 10, 5);
        line(14, 5, 19, 5); line(19, 5, 19, 10);
        line(19, 14, 19, 19); line(19, 19, 14, 19);
        line(10, 19, 5, 19); line(5, 19, 5, 14);
    } else if (action == "maximize") {
        if (floating) { frame(5, 8, 11, 11); line(8, 5, 19, 5); line(19, 5, 19, 16); }
        else frame(5, 5, 14, 14);
    } else if (action == "resize-grip") {
        line(5, 19, 19, 5); line(11, 19, 19, 11); line(17, 19, 19, 17);
    }
    cairo_stroke(cr.get());
    if (cairo_status(cr.get()) != CAIRO_STATUS_SUCCESS) return {};
    cairo_surface_flush(surface.cairo());
    return makeShared<CGLTexture>(DRM_FORMAT_ARGB8888, surface.data(), surface.stride(), surface.size());
}

CHyprBar::CHyprBar(PHLWINDOW pWindow) : IHyprWindowDecoration(pWindow) {
    m_pWindow = pWindow;

    const auto PMONITOR         = pWindow->m_monitor.lock();
    PMONITOR->m_scheduledRecalc = true;

    // button events
    m_pMouseButtonCallback = Event::bus()->m_events.input.mouse.button.listen([&](IPointer::SButtonEvent e, Event::SCallbackInfo& info) { onMouseButton(info, e); });
    m_pTouchDownCallback   = Event::bus()->m_events.input.touch.down.listen([&](ITouch::SDownEvent e, Event::SCallbackInfo& info) { onTouchDown(info, e); });
    m_pTouchUpCallback     = Event::bus()->m_events.input.touch.up.listen([&](ITouch::SUpEvent e, Event::SCallbackInfo& info) { onTouchUp(info, e); });

    // move events
    m_pTouchMoveCallback = Event::bus()->m_events.input.touch.motion.listen([&](ITouch::SMotionEvent e, Event::SCallbackInfo& info) { onTouchMove(info, e); });
    m_pMouseMoveCallback = Event::bus()->m_events.input.mouse.move.listen([&](Vector2D c, Event::SCallbackInfo& info) { onMouseMove(c); });

    Animation::mgr()->createAnimation(configColor(g_pGlobalState->config.barColor->value()), m_cRealBarColor, Config::animationTree()->getAnimationPropertyConfig("border"),
                                      pWindow, AVARDAMAGE_NONE);
    m_cRealBarColor->setUpdateCallback([&](auto) { damageEntire(); });
}

CHyprBar::~CHyprBar() {
    if (m_bDraggingThis) g_layoutManager->endDragTarget();
    std::erase(g_pGlobalState->bars, m_self);
}

// Hyprland reserves a steady top edge. The full window-width strip follows that
// edge while native layout calculation keeps every client below it.
SDecorationPositioningInfo CHyprBar::getPositioningInfo() {
    const auto height = decorationAllowed() ? tabHeight() : 0.;
    m_lastReservedRequest = height;
    SDecorationPositioningInfo info;
    info.policy = DECORATION_POSITION_STICKY;
    info.edges = DECORATION_EDGE_TOP;
    // Place the header inside Hyprland's priority-10000 border. The native
    // border then surrounds the header and client as one continuous frame.
    info.priority = 11000;
    info.reserved = true;
    info.desiredExtents = {{0., height}, {0, 0}};
    return info;
}

void CHyprBar::onPositioningReply(const SDecorationPositioningReply& reply) {
    damageEntire();
    m_assignedBox = reply.assignedGeometry;
    damageEntire();
    if (!reply.ephemeral) scheduleFloatingClearance();
}

std::string CHyprBar::getDisplayName() { return "Gooey"; }

std::string CHyprBar::appName() {
    const auto owner = m_pWindow.lock();
    return owner ? OMousey::windowAppName(owner->m_class, owner->m_title) : "Window";
}

bool CHyprBar::decorationAllowed() {
    const auto owner = m_pWindow.lock();
    return !m_hidden && g_pGlobalState->config.enabled->value() && validMapped(owner) &&
        !owner->m_X11DoesntWantBorders && owner->m_ruleApplicator->decorate().valueOrDefault() &&
        Fullscreen::controller()->getFullscreenModes(owner).internal != Fullscreen::FSMODE_FULLSCREEN;
}

double CHyprBar::reservedHeight() {
    return decorationAllowed() ? std::max(0., m_assignedBox.h) : 0.;
}

CBox CHyprBar::rawAssignedBox() {
    const auto owner = m_pWindow.lock();
    if (!validMapped(owner) || m_assignedBox.w < 1 || m_assignedBox.h < 1) return {};
    CBox box = m_assignedBox;
    box.translate(g_pDecorationPositioner->getEdgeDefinedPoint(DECORATION_EDGE_TOP, owner));
    const auto workspace = owner->m_workspace;
    const auto offset = workspace && !owner->m_pinned ? workspace->m_renderOffset->value() : Vector2D();
    box.translate(offset + owner->m_floatingOffset);
    return box;
}

CBox CHyprBar::clippedAssignedBox() {
    const auto owner = m_pWindow.lock();
    const auto monitor = owner ? owner->m_monitor.lock() : nullptr;
    if (!monitor) return {};
    auto box = rawAssignedBox();
    const auto usable = monitor->m_reservedArea.apply(CBox{monitor->m_position, monitor->m_size});
    if (box.h < 1 || box.y < usable.y - .5 || box.y + box.h > usable.y + usable.h + .5) return {};
    const auto left = std::max(box.x, usable.x);
    const auto right = std::min(box.x + box.w, usable.x + usable.w);
    // Clip to the owner's actual visible edge, never transplant offscreen
    // controls onto another window. Keep room for at least one complete control.
    if (right - left < box.h) return {};
    box.x = left;
    box.w = right - left;
    return box;
}

bool CHyprBar::decorationVisible() {
    if (!decorationAllowed()) return false;
    const auto owner = m_pWindow.lock();
    if (!owner->visible()) return false;
    const auto monitor = owner->m_monitor.lock();
    const auto workspace = owner->m_workspace;
    if (!monitor || (!owner->m_pinned && (!workspace || !workspace->isVisible()))) return false;
    const auto box = clippedAssignedBox();
    return box.w > 0 && box.h > 0;
}

bool CHyprBar::controlsShown() {
    if (!decorationVisible()) return false;
    if (m_bCancelledDown || m_bDraggingThis) return true;
    const auto mouse = g_pInputManager->getMouseCoordsInternal();
    if (assignedBoxGlobal().containsPoint(mouse)) return inputIsValid();
    const auto monitor = State::monitorState()->query().vec(mouse).run();
    if (!monitor) return false;
    Desktop::CViewHitTester hitTester{*Desktop::viewState()};
    if (hitTester.windowAt(mouse, Desktop::View::ALLOW_FLOATING | Desktop::View::RESERVED_EXTENTS) != m_pWindow) return false;
    PHLLS layer = nullptr;
    Vector2D local;
    hitTester.layerSurfaceAt(mouse, &monitor->m_layerSurfaceLayers[ZWLR_LAYER_SHELL_V1_LAYER_TOP], &local, &layer);
    if (layer) return false;
    hitTester.layerSurfaceAt(mouse, &monitor->m_layerSurfaceLayers[ZWLR_LAYER_SHELL_V1_LAYER_OVERLAY], &local, &layer);
    return !layer;
}

void CHyprBar::scheduleFloatingClearance() {
    const auto owner = m_pWindow.lock();
    if (m_clearancePending || !decorationAllowed() || !owner->m_isFloating || owner->m_group || m_bDraggingThis || m_bDragPending) return;
    m_clearancePending = true;
    m_clearanceJob = g_pEventLoopManager->doLaterLock([weak = m_self] {
        // Decorations have unique ownership, so their weak pointers cannot be
        // promoted to shared pointers. This callback runs on the owning event
        // loop; recheck after native move callbacks before touching state again.
        if (weak.expired()) return;
        weak->repairFloatingClearance();
        if (!weak.expired()) weak->m_clearancePending = false;
    });
}

void CHyprBar::repairFloatingClearance() {
    const auto owner = m_pWindow.lock();
    if (!decorationAllowed() || !owner->m_isFloating || owner->m_group || m_bDraggingThis || m_bDragPending ||
        Fullscreen::controller()->isFullscreen(owner) || g_layoutManager->dragController()->target() == owner->layoutTarget()) return;
    const auto monitor = owner->m_monitor.lock();
    if (!monitor || m_assignedBox.h <= 0) return;
    const auto usable = monitor->m_reservedArea.apply(CBox{monitor->m_position, monitor->m_size});
    const auto goal = owner->geometricBox(Desktop::View::IGeometric::GEOMETRIC_GOAL);
    const auto width = goal.w;
    if (width <= 0 || usable.w <= 0 || m_assignedBox.h > usable.h) return;
    const auto x = goal.x;
    const auto y = goal.y + m_assignedBox.y;
    // Preserve ordinary horizontal drags, including partly offscreen windows.
    // Only restore enough visible edge for the three compact controls.
    const auto visibleWidth = std::min({width, usable.w, 3 * m_assignedBox.h});
    const auto minX = usable.x + visibleWidth - width;
    const auto maxX = usable.x + usable.w - visibleWidth;
    const auto dx = std::clamp(x, minX, maxX) - x;
    const auto dy = std::clamp(y, usable.y, usable.y + usable.h - m_assignedBox.h) - y;
    if (std::abs(dx) < .5 && std::abs(dy) < .5) return;
    // A small native position correction exposes a floating window's reserved
    // strip. It runs outside layout callbacks and never fights an active grab.
    const auto weak = m_self;
    const auto moved = Config::Actions::move(Vector2D{dx, dy}, true, owner);
    if (moved && !weak.expired()) weak->damageEntire();
}

bool CHyprBar::inputIsValid() {
    const auto owner = m_pWindow.lock();
    if (!decorationVisible() || owner->isInputBlocked())
        return false;
    if (g_pSeatManager->m_seatGrab && !g_pSeatManager->m_seatGrab->accepts(owner->wlSurface()->resource()))
        return false;

    const auto mouse = g_pInputManager->getMouseCoordsInternal();
    if (!assignedBoxGlobal().containsPoint(mouse)) return false;
    const auto monitor = State::monitorState()->query().vec(mouse).run();
    if (!monitor) return false;

    Desktop::CViewHitTester hitTester{*Desktop::viewState()};
    // Resolve native stacking over the reserved decoration edge, including
    // floating strips above another client. Only our painted strip passed the
    // containment check; the remainder of the reservation takes no input here.
    if (hitTester.windowAt(mouse, Desktop::View::ALLOW_FLOATING | Desktop::View::RESERVED_EXTENTS) != owner) return false;
    if (owner->hasPopupAt(mouse)) return false;

    PHLLS foundSurface = nullptr;
    Vector2D surfaceCoords;
    hitTester.layerSurfaceAt(mouse, &monitor->m_layerSurfaceLayers[ZWLR_LAYER_SHELL_V1_LAYER_TOP], &surfaceCoords, &foundSurface);
    if (foundSurface) return false;
    hitTester.layerSurfaceAt(mouse, &monitor->m_layerSurfaceLayers[ZWLR_LAYER_SHELL_V1_LAYER_OVERLAY], &surfaceCoords, &foundSurface);
    return !foundSurface;
}

void CHyprBar::onMouseButton(Event::SCallbackInfo& info, IPointer::SButtonEvent e) {
    if (e.state != WL_POINTER_BUTTON_STATE_PRESSED) {
        if (m_bCancelledDown && e.button == m_pressedMouseButton)
            handleUpEvent(info);
        return;
    }
    if (info.cancelled || m_bCancelledDown || !inputIsValid() || (e.button != 272 && e.button != 273))
        return;
    m_pressedMouseButton = e.button;
    handleDownEvent(info, std::nullopt);
}
void CHyprBar::onTouchDown(Event::SCallbackInfo&, ITouch::SDownEvent) {}
void CHyprBar::onTouchUp(Event::SCallbackInfo&, ITouch::SUpEvent) {}
void CHyprBar::onTouchMove(Event::SCallbackInfo&, ITouch::SMotionEvent) {}
void CHyprBar::onMouseMove(Vector2D coords) {
    const auto shown = controlsShown();
    if (shown != m_lastControlsShown) { m_lastControlsShown = shown; damageEntire(); }
    const auto hover = inputIsValid() ? buttonAt(cursorRelativeToBar()) : "";
    if (hover != m_hoveredAction) { m_hoveredAction = hover; g_pEventManager->postEvent({"gooeyhover", "changed"}); damageEntire(); }
    if (!m_bCancelledDown || !validMapped(m_pWindow))
        return;
    if (m_pressedMouseButton == 273) {
        const auto local = cursorRelativeToBar();
        if ((coords - m_pressPosition).size() > 8 || !CBox{0, 0, assignedBoxGlobal().w, assignedBoxGlobal().h}.containsPoint(local))
            m_buttonCancelled = true;
        return;
    }
    if (m_pressedAction != "drag-grip" && m_pressedAction != "resize-grip") {
        if (buttonAt(cursorRelativeToBar()) != m_pressedAction)
            m_buttonCancelled = true;
        return;
    }
    if (!m_bDragPending || (coords - m_pressPosition).size() < 5)
        return;
    m_bDragPending = false;
    handleMovement();
}
std::string CHyprBar::buttonAt(Vector2D coords) {
    const auto box = assignedBoxGlobal();
    if (box.w <= 0 || box.h <= 0) return "";
    for (const auto& control : tabControls(box, m_pWindow.lock())) {
        if (!control.action) break;
        if (control.width <= 0) continue;
        const CBox target{control.x, 0, control.width, box.h};
        if (target.containsPoint(coords)) return control.action;
    }
    return "";
}

std::string CHyprBar::hoverAction() {
    return !m_bCancelledDown && !m_bDraggingThis && inputIsValid() ? buttonAt(cursorRelativeToBar()) : "";
}

std::string CHyprBar::buttonState() {
    const auto box = assignedBoxGlobal();
    if (box.w <= 0 || box.h <= 0) return "[]";
    std::string out = "[";
    for (const auto& control : tabControls(box, m_pWindow.lock())) {
        if (!control.action) break;
        if (control.width <= 0) continue;
        if (out.size() > 1) out += ",";
        out += std::format("{{\"action\":\"{}\",\"x\":{},\"y\":{},\"width\":{},\"height\":{}}}", control.action,
            box.x + control.x, box.y, control.width, box.h);
    }
    return out + "]";
}
void CHyprBar::handleDownEvent(Event::SCallbackInfo& info, std::optional<ITouch::SDownEvent>) {
    const auto owner = m_pWindow.lock();
    if (!validMapped(owner)) return;
    const auto coords = cursorRelativeToBar();
    const auto box = assignedBoxGlobal();
    if (!CBox{0, 0, box.w, box.h}.containsPoint(coords)) return;
    if (owner->hasPopupAt(g_pInputManager->getMouseCoordsInternal())) return;
    Desktop::focusState()->fullWindowFocus(owner, Desktop::FOCUS_REASON_CLICK);
    if (owner->m_isFloating) Desktop::windowState()->raise(owner);
    info.cancelled = true;
    m_bCancelledDown = true;
    g_pEventManager->postEvent({"gooeyhover", "pressed"});
    m_buttonCancelled = false;
    m_pressedAction = m_pressedMouseButton == 273 ? "menu-actions" : buttonAt(coords);
    m_pressedArguments = m_pressedAction == "shelf" ? gooeyRestoreDestination(owner) : "";
    m_pressPosition = g_pInputManager->getMouseCoordsInternal();
    m_bDragPending = m_pressedAction == "drag-grip" || m_pressedAction == "resize-grip";
    damageEntire();
}
void CHyprBar::handleUpEvent(Event::SCallbackInfo& info) {
    info.cancelled = true;
    const auto owner = m_pWindow.lock();
    const auto wasDragging = m_bDraggingThis;
    const auto action = m_pressedAction;
    const auto args = m_pressedArguments;
    const auto shouldRun = !wasDragging && !m_buttonCancelled && validMapped(owner) && inputIsValid() &&
        (m_pressedMouseButton == 273 || buttonAt(cursorRelativeToBar()) == action);
    if (m_bDraggingThis) g_layoutManager->endDragTarget();
    m_bDraggingThis = false;
    m_bDragPending = false;
    m_bCancelledDown = false;
    m_pressedAction.clear();
    m_pressedArguments.clear();
    scheduleFloatingClearance();
    damageEntire();
    if (shouldRun && !action.empty() && action != "drag-grip")
        gooeyButtonAction(owner, action == "resize-grip" ? "menu-layout" : action, args);
}
void CHyprBar::handleMovement() {
    const auto owner = m_pWindow.lock();
    if (!validMapped(owner) || owner->m_group) return;
    const bool resize = m_pressedAction == "resize-grip";
    auto corner = Layout::CORNER_BOTTOMRIGHT;
    if (resize && gooeyTileLayout(owner) == "dwindle") {
        // Resize toward the interior split, not an immovable monitor edge.
        if (const auto monitor = owner->m_monitor.lock()) {
            const auto usable = monitor->m_reservedArea.apply(CBox{monitor->m_position, monitor->m_size});
            const auto center = owner->positionAnimation()->goal() + owner->sizeAnimation()->goal() / 2;
            const bool left = center.x > usable.x + usable.w / 2;
            const bool top = center.y > usable.y + usable.h / 2;
            corner = top ? (left ? Layout::CORNER_TOPLEFT : Layout::CORNER_TOPRIGHT)
                         : (left ? Layout::CORNER_BOTTOMLEFT : Layout::CORNER_BOTTOMRIGHT);
        }
    }
    g_layoutManager->beginDragTarget(owner->layoutTarget(), resize ? MBIND_RESIZE : MBIND_MOVE,
                                    resize ? std::optional<Layout::eRectCorner>(corner) : std::nullopt);
    m_bDraggingThis = true;
}
void CHyprBar::renderBarButtons(CBox* tabBox, const float scale, const float a) {
    if (!controlsShown()) return;
    const auto& theme = g_pGlobalState->theme;
    const auto logical = assignedBoxGlobal();
    if (logical.w <= 0 || logical.h <= 0) return;
    const auto xScale = tabBox->w / logical.w;
    const auto radius = static_cast<int>(std::round(std::clamp(theme.radius, 0., logical.h / 2) * scale));
    for (const auto& control : tabControls(logical, m_pWindow.lock())) {
        if (!control.action) break;
        if (control.width <= 0) continue;
        const bool hovered = m_hoveredAction == control.action;
        const bool pressed = m_bCancelledDown && !m_buttonCancelled && m_pressedAction == control.action && hovered;
        if (!hovered && !pressed) continue;
        auto fill = pressed ? theme.pressed : theme.hover;
        fill.a *= a;
        CBox box{tabBox->x + control.x * xScale, tabBox->y, control.width * xScale, tabBox->h};
        g_pHyprOpenGL->scissor(*tabBox);
        g_pHyprOpenGL->renderRect(box, fill, {.round = radius, .roundingPower = 2.F});
    }
}

void CHyprBar::renderBarButtonIcons(CBox* tabBox, const float scale, const float a) {
    if (!controlsShown()) return;
    const auto& theme = g_pGlobalState->theme;
    const auto logical = assignedBoxGlobal();
    if (logical.w <= 0 || logical.h <= 0) return;
    const auto xScale = tabBox->w / logical.w;
    const auto foreground = m_bForcedTitleColor.value_or(theme.ready ? theme.foreground : configColor(g_pGlobalState->config.textColor->value()));
    for (const auto& control : tabControls(logical, m_pWindow.lock())) {
        if (!control.action) break;
        if (control.width <= 0) continue;
        const bool drag = std::string_view(control.action) == "drag-grip";
        if (drag) continue;
        const bool hovered = m_hoveredAction == control.action;
        const bool pressed = m_bCancelledDown && !m_buttonCancelled && m_pressedAction == control.action && hovered;
        const float iconScale = std::min(tabBox->h * 0.58 / 24, 1.0 * scale * theme.scale);
        const auto owner = m_pWindow.lock();
        const bool maximized = Fullscreen::controller()->isFullscreen(owner, Fullscreen::FSMODE_MAXIMIZED);
        const bool shelved = owner->m_workspace && owner->m_workspace->getConfigName() == "special:scratchpad";
        const auto key = std::format("{}:{}:{}:{}:{}:{}:{}:{}:{}", control.action, iconScale, theme.revision, foreground.r, foreground.g, foreground.b, foreground.a, maximized, shelved);
        auto& texture = m_iconTextures[key];
        if (!texture) texture = makeActionIcon(control.action, maximized, shelved, iconScale, foreground);
        if (texture) {
            const auto center = drag ? logical.h / 2 : control.x + control.width / 2;
            const CBox iconBox{tabBox->x + center * xScale - texture->m_size.x / 2,
                tabBox->y + (tabBox->h - texture->m_size.y) / 2 + (pressed ? scale : 0), texture->m_size.x, texture->m_size.y};
            g_pHyprOpenGL->renderTexture(texture, iconBox, {.a = a});
        }

    }
}

void CHyprBar::renderTitle(CBox* tabBox, const float scale, const float a) {
    const auto logical = assignedBoxGlobal();
    if (logical.w < 3 * logical.h) return;
    const auto controls = tabControls(logical, m_pWindow.lock());
    const auto& theme = g_pGlobalState->theme;
    const auto xScale = tabBox->w / logical.w;
    const auto& resize = controls[1];
    const auto rightControls = logical.w - controls[2].x - controls[2].width;
    const double available = std::max(logical.h, logical.w - 2 * std::max(controls[0].x, rightControls));
    const double group = titleGroupWidth(m_pWindow.lock(), available, logical.h);
    const auto textWidth = (group - 1.5 * logical.h) * xScale;
    const auto maxWidth = static_cast<int>(std::floor(textWidth));
    if (maxWidth < 4) return;
    const auto fontSize = static_cast<int>(std::round((theme.ready ? theme.fontSize : g_pGlobalState->config.barTextSize->value()) * scale));
    const auto family = theme.ready ? theme.fontFamily : g_pGlobalState->config.barTextFont->value();
    const auto color = m_bForcedTitleColor.value_or(theme.ready ? theme.foreground : configColor(g_pGlobalState->config.textColor->value()));
    const auto name = appName();
    const auto key = std::format("{}:{}:{}:{}:{}:{}:{}:{}", name, family, fontSize, maxWidth, color.r, color.g, color.b, color.a);
    if (key != m_titleKey || !m_titleTexture) {
        m_titleKey = key;
        m_titleTexture = g_pHyprRenderer->renderText(name, color, std::max(1, fontSize), false, family, maxWidth, 400);
    }
    if (!m_titleTexture) return;
    const auto center = resize.x - (group - logical.h) / 2;
    const CBox title{tabBox->x + center * xScale - m_titleTexture->m_size.x / 2,
        tabBox->y + (tabBox->h - m_titleTexture->m_size.y) / 2, m_titleTexture->m_size.x, m_titleTexture->m_size.y};
    g_pHyprOpenGL->renderTexture(m_titleTexture, title, {.a = a});
}
void CHyprBar::draw(PHLMONITOR pMonitor, const float& a) {
    const auto ENABLED = g_pGlobalState->config.enabled->value();

    if (m_bLastEnabledState != ENABLED) {
        m_bLastEnabledState = ENABLED;
        g_pDecorationPositioner->repositionDeco(this);
    }

    if (!decorationVisible()) return;

    auto data = CBarPassElement::SBarData{this, a};
    g_pHyprRenderer->m_renderPass.add(makeUnique<CBarPassElement>(data));
}

void CHyprBar::renderPass(PHLMONITOR monitor, const float& a) {
    const auto owner = m_pWindow.lock();
    if (!validMapped(owner)) return;
    m_bWindowHasFocus = owner == Desktop::focusState()->window();

    const auto& theme = g_pGlobalState->theme;
    const auto destination = m_bForcedBarColor.value_or(theme.ready ? theme.background : configColor(g_pGlobalState->config.barColor->value()));
    if (destination != m_cRealBarColor->goal()) *m_cRealBarColor = destination;
    auto background = m_cRealBarColor->value();
    background.a *= a;
    const auto box = assignedBoxGlobal();
    m_lastDrawnBox = box;
    CBox tabBox = box;
    tabBox.translate(-monitor->m_position).scale(monitor->m_scale).round();
    if (tabBox.w < 1 || tabBox.h < 1) return;

    // Window controls use the same resolved corner, color and interaction tokens
    // as Omarchy's bar; square-corner themes remain square here as well.
    const auto rounding = static_cast<int>(std::round(std::min<double>(owner->rounding(), box.h / 2) * monitor->m_scale));
    // Round only the outer top corners; the bottom joins the client with no seam.
    CBox fillBox = tabBox;
    fillBox.h += rounding;
    g_pHyprOpenGL->scissor(tabBox);
    static auto globalBlur = CConfigValue<Config::BOOL>("decoration:blur:enabled");
    g_pHyprOpenGL->renderRect(fillBox, background, {.round = rounding, .roundingPower = owner->roundingPower(),
        .blur = g_pGlobalState->config.barBlur->value() && *globalBlur && background.a < 1.F, .blurA = a});
    renderBarButtons(&tabBox, monitor->m_scale, a);
    g_pHyprOpenGL->scissor(tabBox);
    renderBarButtonIcons(&tabBox, monitor->m_scale, a);
    renderTitle(&tabBox, monitor->m_scale, a);
    g_pHyprOpenGL->scissor(nullptr);
    m_bButtonsDirty = false;
}

eDecorationType CHyprBar::getDecorationType() {
    return DECORATION_CUSTOM;
}

void CHyprBar::updateWindow(PHLWINDOW pWindow) {
    const auto requested = decorationAllowed() ? tabHeight() : 0.;
    if (std::abs(requested - m_lastReservedRequest) > .01) g_pDecorationPositioner->repositionDeco(this);
    scheduleFloatingClearance();
    damageEntire();
}

void CHyprBar::onConfigReloaded() {
    m_bButtonsDirty      = true;
    m_iconTextures.clear();
    m_titleTexture.reset();
    m_titleKey.clear();

    g_pDecorationPositioner->repositionDeco(this);
    scheduleFloatingClearance();
    damageEntire();
}

void CHyprBar::damageEntire() {
    auto previous = m_lastDrawnBox;
    if (previous.w > 0 && previous.h > 0) g_pHyprRenderer->damageBox(previous.expand(2));
    g_pHyprRenderer->damageBox(assignedBoxGlobal().expand(2));
}

Vector2D CHyprBar::cursorRelativeToBar() {
    return g_pInputManager->getMouseCoordsInternal() - assignedBoxGlobal().pos();
}

eDecorationLayer CHyprBar::getDecorationLayer() {
    return DECORATION_LAYER_OVER;
}

uint64_t CHyprBar::getDecorationFlags() {
    // The reserved edge is part of native layout geometry; hooks consume only
    // the visible strip and still defer to native window and layer ownership.
    return DECORATION_PART_OF_MAIN_WINDOW;
}

CBox CHyprBar::assignedBoxGlobal() {
    return decorationVisible() ? clippedAssignedBox() : CBox{};
}

PHLWINDOW CHyprBar::getOwner() {
    return m_pWindow.lock();
}

void CHyprBar::updateRules() {
    const auto PWINDOW              = m_pWindow.lock();
    auto       prevHidden           = m_hidden;

    m_bForcedBarColor   = std::nullopt;
    m_bForcedTitleColor = std::nullopt;
    m_hidden            = false;

    if (PWINDOW->m_ruleApplicator->m_otherProps.props.contains(g_pGlobalState->nobarRuleIdx))
        m_hidden = truthy(PWINDOW->m_ruleApplicator->m_otherProps.props.at(g_pGlobalState->nobarRuleIdx)->effect);
    if (PWINDOW->m_ruleApplicator->m_otherProps.props.contains(g_pGlobalState->barColorRuleIdx))
        m_bForcedBarColor = CHyprColor(Config::ParserUtils::parseColor(PWINDOW->m_ruleApplicator->m_otherProps.props.at(g_pGlobalState->barColorRuleIdx)->effect).value_or(0));
    if (PWINDOW->m_ruleApplicator->m_otherProps.props.contains(g_pGlobalState->titleColorRuleIdx))
        m_bForcedTitleColor = CHyprColor(Config::ParserUtils::parseColor(PWINDOW->m_ruleApplicator->m_otherProps.props.at(g_pGlobalState->titleColorRuleIdx)->effect).value_or(0));

    if (prevHidden != m_hidden)
        g_pDecorationPositioner->repositionDeco(this);
    m_iconTextures.clear();
    damageEntire();
}
