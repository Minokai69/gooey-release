#define _GNU_SOURCE
// Test-only physical-keycode keyboard on the nested Wayland connection.
#include <wayland-client.h>
#include <xkbcommon/xkbcommon.h>
#include <sys/mman.h>
#include <unistd.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include "virtual-keyboard.h"

static struct zwp_virtual_keyboard_manager_v1 *manager;
static struct wl_seat *seat;
static void global(void *data, struct wl_registry *r, uint32_t name, const char *iface, uint32_t version) {
    (void)data; (void)version;
    if (!strcmp(iface, zwp_virtual_keyboard_manager_v1_interface.name))
        manager=wl_registry_bind(r,name,&zwp_virtual_keyboard_manager_v1_interface,1);
    if (!strcmp(iface,wl_seat_interface.name)) seat=wl_registry_bind(r,name,&wl_seat_interface,1);
}
static void removed(void *data, struct wl_registry *r, uint32_t name) {(void)data;(void)r;(void)name;}
static const struct wl_registry_listener listener={global,removed};
static uint32_t now(void) {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC,&t);
    return (uint32_t)(t.tv_sec*1000+t.tv_nsec/1000000);
}
int main(int argc,char **argv) {
    const char *preview=getenv("OMARCHY_MOUSE_PREVIEW"), *display_name=getenv("WAYLAND_DISPLAY");
    if (!preview || strcmp(preview,"1") || !display_name || !strcmp(display_name,"/run/host-wayland")) return 2;
    struct wl_display *display=wl_display_connect(NULL);
    if (!display) return 2;
    wl_registry_add_listener(wl_display_get_registry(display),&listener,NULL);
    wl_display_roundtrip(display);
    if (!manager || !seat) return 2;
    struct xkb_context *context=xkb_context_new(XKB_CONTEXT_NO_FLAGS);
    const struct xkb_rule_names names={.rules="evdev",.model="pc105",.layout="us"};
    struct xkb_keymap *keymap=xkb_keymap_new_from_names(context,&names,XKB_KEYMAP_COMPILE_NO_FLAGS);
    struct xkb_state *state=xkb_state_new(keymap);
    char *text=xkb_keymap_get_as_string(keymap,XKB_KEYMAP_FORMAT_TEXT_V1);
    size_t size=strlen(text)+1;
    int fd=memfd_create("gooey-test-keymap",MFD_CLOEXEC);
    if (fd<0 || write(fd,text,size)!=(ssize_t)size) return 2;
    struct zwp_virtual_keyboard_v1 *keyboard=zwp_virtual_keyboard_manager_v1_create_virtual_keyboard(manager,seat);
    zwp_virtual_keyboard_v1_keymap(keyboard,WL_KEYBOARD_KEYMAP_FORMAT_XKB_V1,fd,size);
    wl_display_roundtrip(display); close(fd); free(text);
    for (int i=1;i<argc;i++) {
        if (!strcmp(argv[i],"sleep") && i+1<argc) usleep((useconds_t)atoi(argv[++i])*1000);
        else if ((!strcmp(argv[i],"down") || !strcmp(argv[i],"up")) && i+1<argc) {
            int down=!strcmp(argv[i],"down"); unsigned key=(unsigned)atoi(argv[++i]);
            zwp_virtual_keyboard_v1_key(keyboard,now(),key,down?WL_KEYBOARD_KEY_STATE_PRESSED:WL_KEYBOARD_KEY_STATE_RELEASED);
            xkb_state_update_key(state,key+8,down?XKB_KEY_DOWN:XKB_KEY_UP);
            zwp_virtual_keyboard_v1_modifiers(keyboard,
                xkb_state_serialize_mods(state,XKB_STATE_MODS_DEPRESSED),
                xkb_state_serialize_mods(state,XKB_STATE_MODS_LATCHED),
                xkb_state_serialize_mods(state,XKB_STATE_MODS_LOCKED),
                xkb_state_serialize_layout(state,XKB_STATE_LAYOUT_EFFECTIVE));
        } else {fprintf(stderr,"Expected down/up KEYCODE or sleep MS\n");return 2;}
        wl_display_roundtrip(display);
    }
    zwp_virtual_keyboard_v1_destroy(keyboard);
    wl_display_roundtrip(display); wl_display_disconnect(display);
    xkb_state_unref(state);xkb_keymap_unref(keymap);xkb_context_unref(context);
    return 0;
}
