#pragma once

#include <string>
#include <string_view>

namespace OMousey {
inline bool identityWhitespace(char c) {
    return c == ' ' || c == '\t' || c == '\r' || c == '\n' || c == '\f' || c == '\v';
}

inline std::string cleanIdentity(std::string_view text, bool classSeparators) {
    std::string result;
    bool pendingSpace = false;
    for (const auto c : text) {
        if (identityWhitespace(c) || (classSeparators && (c == '-' || c == '_'))) {
            pendingSpace = !result.empty();
            continue;
        }
        if (pendingSpace) result += ' ';
        result += c;
        pendingSpace = false;
    }
    return result;
}

inline std::string windowAppName(std::string_view appClass, std::string_view title) {
    if (appClass.ends_with(".desktop")) appClass.remove_suffix(8);

    // Omarchy's --app=URL launchers use Chromium's chrome-host__-profile
    // class. Keep the website identity intact before shortening desktop IDs.
    if (appClass.starts_with("chrome-")) {
        const auto separator = appClass.find("__-", 7);
        if (separator != std::string_view::npos && separator > 7 && separator + 3 < appClass.size()) {
            const auto host = appClass.substr(7, separator - 7);
            bool validHost = true;
            for (const auto c : host) {
                if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
                      (c >= '0' && c <= '9') || c == '.' || c == '-')) {
                    validHost = false;
                    break;
                }
            }
            if (validHost) return std::string(host);
        }
    }

    const auto dot = appClass.find_last_of('.');
    if (dot != std::string_view::npos && dot + 1 < appClass.size()) appClass.remove_prefix(dot + 1);
    auto name = cleanIdentity(appClass, true);
    if (name == "chatgpt") return "ChatGPT";
    if (!name.empty() && name.front() >= 'a' && name.front() <= 'z') name.front() -= 'a' - 'A';
    if (name.empty()) name = cleanIdentity(title, false);
    return name.empty() ? "Window" : name;
}
}
