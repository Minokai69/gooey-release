#pragma once

#define WLR_USE_UNSTABLE

#include <hyprland/src/render/decorations/IHyprWindowDecoration.hpp>
#include <hyprland/src/render/OpenGL.hpp>
#include <hyprland/src/render/gl/GLTexture.hpp>
#include <hyprland/src/devices/IPointer.hpp>
#include <hyprland/src/devices/ITouch.hpp>
#include <hyprland/src/desktop/rule/windowRule/WindowRule.hpp>
#include <hyprland/src/helpers/AnimatedVariable.hpp>
#include <hyprland/src/helpers/time/Time.hpp>
#include <hyprland/src/helpers/signal/Signal.hpp>
#include <hyprland/src/managers/eventLoop/EventLoopManager.hpp>
#include "globals.hpp"
#include <unordered_map>

#define private public
#include <hyprland/src/managers/input/InputManager.hpp>
#undef private

namespace Event {
    struct SCallbackInfo;
}

class CHyprBar : public IHyprWindowDecoration {
  public:
    CHyprBar(PHLWINDOW);
    virtual ~CHyprBar();

    virtual SDecorationPositioningInfo getPositioningInfo();

    virtual void                       onPositioningReply(const SDecorationPositioningReply& reply);

    virtual void                       draw(PHLMONITOR, float const& a);

    virtual eDecorationType            getDecorationType();

    virtual void                       updateWindow(PHLWINDOW);

    virtual void                       damageEntire();

    virtual eDecorationLayer           getDecorationLayer();

    virtual uint64_t                   getDecorationFlags();

    bool                               m_bButtonsDirty = true;

    virtual std::string                getDisplayName();

    PHLWINDOW                          getOwner();
    bool                               decorationVisible();
    bool                               controlsShown();
    double                             reservedHeight();
    std::string                        appName();
    CBox menuAnchor() { return assignedBoxGlobal(); }
    std::string buttonState();
    std::string hoverAction();

    void                               updateRules();
    void                               onConfigReloaded();

    WP<CHyprBar>                       m_self;

  private:
    PHLWINDOWREF               m_pWindow;

    CBox                       m_lastDrawnBox;
    CBox                       m_assignedBox;
    double                     m_lastReservedRequest = -1;
    bool                       m_lastControlsShown = false;
    bool                       m_clearancePending = false;
    UP<SEventLoopDoLaterLock>   m_clearanceJob;
    SP<Render::ITexture>       m_titleTexture;
    std::string                m_titleKey;

    bool                       m_hidden             = false;
    bool                       m_bLastEnabledState  = false;
    bool                       m_bWindowHasFocus    = false;
    std::optional<CHyprColor>  m_bForcedBarColor;
    std::optional<CHyprColor>  m_bForcedTitleColor;

    PHLANIMVAR<CHyprColor>     m_cRealBarColor;

    Vector2D                   cursorRelativeToBar();

    void                       renderPass(PHLMONITOR, float const& a);
    void renderBarButtons(CBox* barBox, const float scale, const float a);
    void renderBarButtonIcons(CBox* barBox, const float scale, const float a);
    void renderTitle(CBox* barBox, const float scale, const float a);
    bool decorationAllowed();
    CBox rawAssignedBox();
    CBox clippedAssignedBox();
    void scheduleFloatingClearance();
    void repairFloatingClearance();

    bool inputIsValid();
    void onMouseButton(Event::SCallbackInfo& info, IPointer::SButtonEvent e);
    void onTouchDown(Event::SCallbackInfo& info, ITouch::SDownEvent e);
    void onTouchUp(Event::SCallbackInfo& info, ITouch::SUpEvent e);
    void onMouseMove(Vector2D coords);
    void onTouchMove(Event::SCallbackInfo& info, ITouch::SMotionEvent e);

    void handleDownEvent(Event::SCallbackInfo& info, std::optional<ITouch::SDownEvent> touchEvent);
    void handleUpEvent(Event::SCallbackInfo& info);
    void handleMovement();
    std::string buttonAt(Vector2D coords);

    CBox assignedBoxGlobal();

    CHyprSignalListener m_pMouseButtonCallback;
    CHyprSignalListener m_pTouchDownCallback;
    CHyprSignalListener m_pTouchUpCallback;

    CHyprSignalListener m_pTouchMoveCallback;
    CHyprSignalListener m_pMouseMoveCallback;

    std::string m_hoveredAction;
    std::string m_pressedAction;
    std::string m_pressedArguments;
    uint32_t m_pressedMouseButton = 0;
    bool m_buttonCancelled = false;
    Vector2D m_pressPosition;
    std::unordered_map<std::string, SP<Render::ITexture>> m_iconTextures;
    bool                m_bDraggingThis  = false;
    bool                m_bDragPending   = false;
    bool                m_bCancelledDown = false;

    friend class CBarPassElement;
};
