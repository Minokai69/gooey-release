// Virtual pointer for nested Gooey integration tests only.
#include <wayland-client.h>
#include <linux/input-event-codes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include "virtual-pointer.h"

static struct zwlr_virtual_pointer_manager_v1 *manager;
static void global(void *data, struct wl_registry *registry, uint32_t name,
                   const char *interface, uint32_t version) {
    (void)data;
    if (!strcmp(interface, zwlr_virtual_pointer_manager_v1_interface.name))
        manager = wl_registry_bind(registry, name, &zwlr_virtual_pointer_manager_v1_interface, version < 2 ? version : 2);
}
static void removed(void *data, struct wl_registry *registry, uint32_t name) {
    (void)data; (void)registry; (void)name;
}
static const struct wl_registry_listener listener = {global, removed};
static uint32_t now(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint32_t)(ts.tv_sec * 1000 + ts.tv_nsec / 1000000);
}
int main(int argc, char **argv) {
    const char *preview = getenv("OMARCHY_MOUSE_PREVIEW");
    const char *display_name = getenv("WAYLAND_DISPLAY");
    if (!preview || strcmp(preview, "1") || !display_name || !strcmp(display_name, "/run/host-wayland")) {
        fprintf(stderr, "Only available in the nested Gooey desktop.\n"); return 2;
    }
    struct wl_display *display = wl_display_connect(NULL);
    if (!display) return 2;
    struct wl_registry *registry = wl_display_get_registry(display);
    wl_registry_add_listener(registry, &listener, NULL);
    wl_display_roundtrip(display);
    if (!manager) { fprintf(stderr, "No virtual pointer protocol.\n"); return 2; }
    struct zwlr_virtual_pointer_v1 *pointer = zwlr_virtual_pointer_manager_v1_create_virtual_pointer(manager, NULL);
    for (int i = 1; i < argc; ++i) {
        if (!strcmp(argv[i], "move") && i + 4 < argc) {
            uint32_t x = (uint32_t)atoi(argv[++i]), y = (uint32_t)atoi(argv[++i]);
            uint32_t w = (uint32_t)atoi(argv[++i]), h = (uint32_t)atoi(argv[++i]);
            zwlr_virtual_pointer_v1_motion_absolute(pointer, now(), x, y, w, h);
        } else if (!strcmp(argv[i], "down") || !strcmp(argv[i], "rightdown")) {
            zwlr_virtual_pointer_v1_button(pointer, now(), !strcmp(argv[i], "down") ? BTN_LEFT : BTN_RIGHT, WL_POINTER_BUTTON_STATE_PRESSED);
        } else if (!strcmp(argv[i], "up") || !strcmp(argv[i], "rightup")) {
            zwlr_virtual_pointer_v1_button(pointer, now(), !strcmp(argv[i], "up") ? BTN_LEFT : BTN_RIGHT, WL_POINTER_BUTTON_STATE_RELEASED);
        } else if (!strcmp(argv[i], "wheel") && i + 1 < argc) {
            zwlr_virtual_pointer_v1_axis(pointer, now(), WL_POINTER_AXIS_VERTICAL_SCROLL, wl_fixed_from_int(atoi(argv[++i])));
        } else if (!strcmp(argv[i], "sleep") && i + 1 < argc) {
            usleep((useconds_t)atoi(argv[++i]) * 1000);
        } else {
            fprintf(stderr, "Unknown input command: %s\n", argv[i]); return 2;
        }
        zwlr_virtual_pointer_v1_frame(pointer);
        wl_display_roundtrip(display);
    }
    zwlr_virtual_pointer_v1_destroy(pointer);
    wl_display_roundtrip(display);
    wl_display_disconnect(display);
    return 0;
}
