#pragma once
#include "globals.hpp"
#include <hyprland/src/desktop/DesktopTypes.hpp>
void gooeyDefaultButtons();
void gooeyRegister();
void gooeyButtonAction(PHLWINDOW owner, const std::string& action, const std::string& args = "");
std::string gooeyButtonLabel(PHLWINDOW owner, const std::string& action);

std::string gooeyRestoreDestination(PHLWINDOW owner);

std::string gooeyButtonDescription(PHLWINDOW owner, const std::string& action);

std::string gooeyTileLayout(PHLWINDOW owner);
struct GooeyResizeAxes { bool horizontal = false; bool vertical = false; };
GooeyResizeAxes gooeyResizeAxes(PHLWINDOW owner);
