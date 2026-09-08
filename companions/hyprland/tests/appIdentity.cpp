#include "appIdentity.hpp"

#include <array>
#include <iostream>

int main() {
    struct Case { std::string_view appClass; std::string_view title; std::string_view expected; };
    const std::array cases{
        Case{"chrome-x.com__-Default", "Home / X", "x.com"},
        Case{"chrome-my-site.example.com__-Profile_2", "Page title", "my-site.example.com"},
        Case{"chrome-localhost__-Default", "Local app", "localhost"},
        Case{"org.omarchy.agent", "Assistant session", "Agent"},
        Case{"chatgpt", "Conversation title", "ChatGPT"},
        Case{"foot", "shell", "Foot"},
        Case{"org.gnome.Nautilus.desktop", "Downloads", "Nautilus"},
        Case{"  my__app---name \t", "Other title", "My app name"},
        Case{"日本語__app", "Other title", "日本語 app"},
        Case{"", "  Document - editor\n ", "Document - editor"},
        Case{"__-- \t", "\n", "Window"},
    };
    for (const auto& test : cases) {
        const auto actual = OMousey::windowAppName(test.appClass, test.title);
        if (actual != test.expected) {
            std::cerr << "App identity mismatch for '" << test.appClass << "': expected '"
                      << test.expected << "', got '" << actual << "'\n";
            return 1;
        }
    }
    std::cout << cases.size() << " app identity cases passed\n";
}
