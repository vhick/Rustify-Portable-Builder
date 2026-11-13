// Rustify PortableApps root launcher (GPL-3.0-or-later).
// No registry edits, no global environment changes. Launch one child and wait.
// All paths come from GetModuleFileNameW, never CWD. Windows 10/11 x64.
#define UNICODE
#define _UNICODE
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <shellapi.h>
#include <string>
#include <vector>

static void error(const wchar_t* title, const wchar_t* msg) {
    MessageBoxW(nullptr, msg, title, MB_OK | MB_ICONERROR | MB_SETFOREGROUND);
}
static bool directory_ok(const std::wstring& p) {
    DWORD attr = GetFileAttributesW(p.c_str());
    if (attr == INVALID_FILE_ATTRIBUTES) {
        if (!CreateDirectoryW(p.c_str(), nullptr) && GetLastError() != ERROR_ALREADY_EXISTS) return false;
        attr = GetFileAttributesW(p.c_str());
    }
    // Reparse points can redirect portable data to installed-app or shared host state.
    return attr != INVALID_FILE_ATTRIBUTES && (attr & FILE_ATTRIBUTE_DIRECTORY) && !(attr & FILE_ATTRIBUTE_REPARSE_POINT);
}
static bool exists_file(const std::wstring& p) {
    DWORD a = GetFileAttributesW(p.c_str());
    return a != INVALID_FILE_ATTRIBUTES && !(a & FILE_ATTRIBUTE_DIRECTORY) && !(a & FILE_ATTRIBUTE_REPARSE_POINT);
}
// Quote arguments following CommandLineToArgvW / CRT Windows quote-backslash rules.
static std::wstring quote(const std::wstring& s) {
    std::wstring out=L"\"";
    size_t slash=0;
    for (wchar_t c: s) {
        if (c == L'\\') { ++slash; continue; }
        if (c == L'"') { out.append(slash*2+1, L'\\'); out += L'"'; slash=0; continue; }
        out.append(slash, L'\\'); slash=0; out += c;
    }
    out.append(slash*2, L'\\'); out += L'"';
    return out;
}
int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR, int) {
    std::vector<wchar_t> path(32768);
    DWORD n=GetModuleFileNameW(nullptr, path.data(), static_cast<DWORD>(path.size()));
    if (!n || n >= path.size()) { error(L"Rustify Portable", L"Could not locate portable launcher."); return 10; }
    std::wstring root(path.data(), n);
    auto pos = root.find_last_of(L"\\/");
    if (pos == std::wstring::npos) { error(L"Rustify Portable", L"Invalid launcher path."); return 11; }
    root.resize(pos);
    std::wstring data = root + L"\\Data";
    std::wstring profile = data + L"\\RustifyProfile";
    if (!directory_ok(data) || !directory_ok(profile)) {
        error(L"Rustify Portable", L"Data folder is inaccessible or redirected by a junction/symlink. No host profiles were changed.");
        return 12;
    }
    if (!directory_ok(profile + L"\\data") || !directory_ok(profile + L"\\data\\settings") ||
        !directory_ok(profile + L"\\cache")) {
        error(L"Rustify Portable", L"A portable profile subdirectory is inaccessible or is a symlink/junction. Launch aborted without touching host state.");
        return 12;
    }
    std::wstring appDir = root + L"\\App\\Rustify";
    std::wstring exe = appDir + L"\\Rustify.exe";
    if (!exists_file(exe)) {
        error(L"Rustify Portable", L"App\\Rustify\\Rustify.exe is missing. Reinstall App files without deleting Data.");
        return 13;
    }
    if (!SetEnvironmentVariableW(L"RUSTIFY_PORTABLE_DIR", profile.c_str())) {
        error(L"Rustify Portable", L"Could not initialize Rustify's portable profile environment."); return 14;
    }
    // Upstream chooses this BEFORE first Kotlin settings or CoreLoader initialization.
    // A stable marker is also supplied with the official distribution as a fallback.
    int argc=0;
    LPWSTR* argv=CommandLineToArgvW(GetCommandLineW(), &argc);
    std::wstring cmd=quote(exe);
    if (argv) { for (int i=1;i<argc;i++) { cmd += L" "; cmd += quote(argv[i]); } LocalFree(argv); }
    std::vector<wchar_t> mutableCmd(cmd.begin(), cmd.end());
    mutableCmd.push_back(0);
    STARTUPINFOW si{}; si.cb=sizeof(si);
    PROCESS_INFORMATION pi{};
    BOOL started=CreateProcessW(exe.c_str(), mutableCmd.data(), nullptr, nullptr, FALSE,
                                0, nullptr, appDir.c_str(), &si, &pi);
    if (!started) { error(L"Rustify Portable", L"Could not launch upstream Rustify.exe. Verify complete App contents and Windows compatibility."); return 15; }
    CloseHandle(pi.hThread);
    // Do not kill tray/background children and do not touch installed Rustify.
    // One upstream process per profile is managed by its own SingleInstance class.
    WaitForSingleObject(pi.hProcess, INFINITE);
    DWORD code=0;
    if (!GetExitCodeProcess(pi.hProcess, &code)) code=16;
    CloseHandle(pi.hProcess);
    return static_cast<int>(code);
}
