#pragma once

#include <hyprland/src/plugins/PluginAPI.hpp>
#include <hyprland/src/render/Texture.hpp>
#include <hyprland/src/config/values/types/BoolValue.hpp>
#include <hyprland/src/config/values/types/IntValue.hpp>
#include <hyprland/src/config/values/types/StringValue.hpp>
#include <hyprland/src/config/values/types/ColorValue.hpp>
#include <hyprland/src/config/values/types/FontWeightValue.hpp>

inline HANDLE PHANDLE = nullptr;

struct SHyprButton {
    std::string          cmd     = "";
    bool                 userfg  = false;
    CHyprColor           fgcol   = CHyprColor(0, 0, 0, 0);
    CHyprColor           bgcol   = CHyprColor(0, 0, 0, 0);
    float                size    = 10;
    std::string          icon    = "";
    SP<Render::ITexture> iconTex;
};

class CHyprBar;

struct SGlobalState {
    // Resolved by Omarchy's Color/Style singletons, delivered by the owned QML
    // service. Neutral defaults are only for the short interval before sync.
    struct STheme {
        bool ready = false;
        uint64_t revision = 0;
        CHyprColor background{0xff181818}, foreground{0xffeeeeee}, accent{0xffeeeeee}, muted{0xffaaaaaa}, danger{0xffff6666};
        CHyprColor border{0xff555555}, normal{0x0aeeeeee}, hover{0x14eeeeee}, pressed{0x38eeeeee};
        CHyprColor normalBorder{0x66555555}, hoverBorder{0x40eeeeee};
        double normalBorderWidth = 1, hoverBorderWidth = 1, radius = 0, scale = 1, height = 32, fontSize = 12;
        std::string fontFamily = "Sans";
    } theme;
    std::vector<SHyprButton>  buttons;
    std::vector<WP<CHyprBar>> bars;
    uint32_t                  nobarRuleIdx      = 0;
    uint32_t                  barColorRuleIdx   = 0;
    uint32_t                  titleColorRuleIdx = 0;

    struct {
        SP<Config::Values::CColorValue>      barColor, textColor, inactiveButtonColor;
        SP<Config::Values::CIntValue>        barHeight;
        SP<Config::Values::CIntValue>        barTextSize;
        SP<Config::Values::CFontWeightValue> barTextWeight;
        SP<Config::Values::CIntValue>        barPadding;
        SP<Config::Values::CIntValue>        barButtonPadding;
        SP<Config::Values::CBoolValue>       barBlur, barTitleEnabled, barPartOfWindow, barPrecedenceOverBorder, enabled, iconOnHover;
        SP<Config::Values::CStringValue>     barTextFont, barTextAlign, barButtonsAlignment;
    } config;
};

inline UP<SGlobalState> g_pGlobalState;
