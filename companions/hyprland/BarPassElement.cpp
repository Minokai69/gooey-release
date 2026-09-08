#include "BarPassElement.hpp"
#include <hyprland/src/render/OpenGL.hpp>
#include <hyprland/src/render/Renderer.hpp>
#include "barDeco.hpp"

using namespace Render::GL;

CBarPassElement::CBarPassElement(const CBarPassElement::SBarData& data_) : data(data_) {
    ;
}

std::vector<UP<IPassElement>> CBarPassElement::draw() {
    data.deco->renderPass(g_pHyprRenderer->m_renderData.pMonitor.lock(), data.a);
    return {};
}

bool CBarPassElement::needsLiveBlur() {
    static auto PENABLEBLURGLOBAL = CConfigValue<Config::BOOL>("decoration:blur:enabled");
    if (!g_pGlobalState->config.barBlur->value() || !*PENABLEBLURGLOBAL)
        return false;

    const auto& theme = g_pGlobalState->theme;
    const auto destination = data.deco->m_bForcedBarColor.value_or(theme.ready ? theme.background :
        CHyprColor{static_cast<uint64_t>(g_pGlobalState->config.barColor->value())});
    // renderPass sets the destination after preparation. Include it in case
    // animation settings immediately apply a new translucent theme color.
    const auto current = data.deco->m_cRealBarColor->value();
    return current.a * data.a < 1.F || destination.a * data.a < 1.F;
}

std::optional<CBox> CBarPassElement::boundingBox() {
    // Temporary fix: expand the bar bb a bit, otherwise occlusion gets too aggressive.
    return data.deco->assignedBoxGlobal().translate(-g_pHyprRenderer->m_renderData.pMonitor->m_position).expand(10);
}

bool CBarPassElement::needsPrecomputeBlur() {
    return false;
}
