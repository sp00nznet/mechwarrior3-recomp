/*
 * MechWarrior 3 - static recompilation host.
 *
 * A 32-bit host on pcrecomp's runtime/native32 (the native bridge, callbacks
 * and the machine lock; see its header). The lifted Mech3.exe calls the real
 * MFC42.DLL, DirectDraw, DirectSound and DirectInput through the bridge;
 * what is here is only what is specific to this game: the guest image, its
 * folder, its command line and the fault report. docs/architecture.md has
 * the reasoning.
 *
 * Linked at /BASE:0x60000000 (CMakeLists.txt) so 0x00400000 (Mech3.exe) is
 * free when main() maps the image.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <vfw.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "native32.h"
#include "recomp_trace.h"

extern const uint32_t mw3_entry_va;      /* recomp_dispatch.c */

#define MW3_BASE 0x00400000u

static DWORD g_watchdog_s;
static char  g_game[MAX_PATH];           /* the game folder, with a trailing '\' */
static char  g_guest_exe[MAX_PATH], g_guest_cmdline[MAX_PATH + 3];

#define ARG(n) MEM32(g_esp + 4 + 4 * (n))
#define RET(v, nargs) do { g_eax = (uint32_t)(v); g_esp += 4 + 4 * (nargs); } while (0)

/* ------------------------------------------------------------- the guest */

/* The guest is Mech3.exe in the game folder, not this host: its hInstance
 * (icons, dialogs, strings) is GetModuleHandleA(NULL). The CRT startup passes
 * it on to MFC's AfxWinMain, which takes its resources from there. */
static void shim_GetModuleHandleA(void) {
    uint32_t name = ARG(0);
    RET(name ? (uint32_t)(uintptr_t)GetModuleHandleA((const char*)(uintptr_t)name) : MW3_BASE, 1);
}

/* GetModuleFileNameA for the guest's handle (or NULL): Mech3.exe, not this
 * host. -1 if h is some other module. */
static int guest_file_name(uint32_t h, char* out, uint32_t size) {
    if (h != 0 && h != MW3_BASE) return -1;
    uint32_t n = (uint32_t)strlen(g_guest_exe);
    if (size) {
        if (n >= size) n = size - 1;
        memcpy(out, g_guest_exe, n);
        out[n] = 0;
    }
    return (int)n;
}

static void shim_GetModuleFileNameA(void) {
    uint32_t h = ARG(0), size = ARG(2);
    char* out = (char*)(uintptr_t)ARG(1);
    int n = guest_file_name(h, out, size);
    RET(n >= 0 ? (uint32_t)n : GetModuleFileNameA((HMODULE)(uintptr_t)h, out, size), 3);
}

/* The same, for native MFC42.DLL: CWinApp::SetCurrentHandles asks for
 * m_hInstance's file name, then writes through strrchr(name, '.'). The real
 * call does not know 0x00400000 (mapped, not loaded), returns "" and MFC
 * writes to NULL. */
static DWORD WINAPI native_GetModuleFileNameA(HMODULE h, LPSTR out, DWORD size) {
    int n = guest_file_name((uint32_t)(uintptr_t)h, out, size);
    return n >= 0 ? (DWORD)n : GetModuleFileNameA(h, out, size);
}

/* Point one import of a natively loaded DLL at fn. 0 if not found. */
static int patch_native_import(const char* module, const char* name, void* fn) {
    uint8_t* b = (uint8_t*)GetModuleHandleA(module);
    if (!b) return 0;
    IMAGE_NT_HEADERS32* nt = (IMAGE_NT_HEADERS32*)(b + ((IMAGE_DOS_HEADER*)b)->e_lfanew);
    IMAGE_DATA_DIRECTORY dd = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    for (IMAGE_IMPORT_DESCRIPTOR* d = (IMAGE_IMPORT_DESCRIPTOR*)(b + dd.VirtualAddress);
         dd.VirtualAddress && d->Name; d++) {
        uint32_t* names = (uint32_t*)(b + (d->OriginalFirstThunk ? d->OriginalFirstThunk : d->FirstThunk));
        uint32_t* iat = (uint32_t*)(b + d->FirstThunk);
        for (int i = 0; names[i]; i++) {
            if (IMAGE_SNAP_BY_ORDINAL32(names[i])) continue;
            if (strcmp(((IMAGE_IMPORT_BY_NAME*)(b + names[i]))->Name, name)) continue;
            DWORD old;
            VirtualProtect(&iat[i], 4, PAGE_READWRITE, &old);
            iat[i] = (uint32_t)(uintptr_t)fn;
            VirtualProtect(&iat[i], 4, old, &old);
            return 1;
        }
    }
    return 0;
}

static void shim_GetCommandLineA(void) { RET((uintptr_t)g_guest_cmdline, 0); }

static void shim_ExitProcess(void) {
    fprintf(stderr, "[exit] ExitProcess(%u)\n", ARG(0));
    fflush(stderr);
    ExitProcess(ARG(0));
}

/* The CD check (sub_0056F770) walks the drive roots for a CD-ROM with
 * video\c1.avi, and the movie loaders fall back to it. The game folder holds
 * the disc's files, so it is the only drive, and it is a CD-ROM. These two
 * imports have no other callers. */
static void shim_GetLogicalDriveStringsA(void) {
    uint32_t size = ARG(0), n = (uint32_t)strlen(g_game);
    char* out = (char*)(uintptr_t)ARG(1);
    if (n + 2 > size) { RET(n + 2, 2); return; }
    memcpy(out, g_game, n + 1);
    out[n + 1] = 0;
    RET(n + 1, 2);
}

static void shim_GetDriveTypeA(void) {
    const char* root = (const char*)(uintptr_t)ARG(0);
    RET(root && !_stricmp(root, g_game) ? DRIVE_CDROM : GetDriveTypeA(root), 1);
}

/* The installer's key, HKLM\SOFTWARE\MicroProse\MechWarrior 3\1.0, holds
 * InstallOptions: a mask of the installed components (sub_00591370 tests
 * it). Bits 0x1/0x2/0x4 are the hardware renderer's file sets, 0x100/0x200/
 * 0x400 the software renderer's, 0x10000 and 0x40000 two more; with none the
 * game stops at "Software Render Files ... not installed". The game folder is
 * a full install, so every bit the game tests is set. The key is read from
 * HKCU instead (no installer, no admin), next to the game's own settings. */
#define MW3_KEY "SOFTWARE\\MicroProse\\MechWarrior 3\\1.0"
#define MW3_INSTALL_OPTIONS 0x50707u

static void shim_RegOpenKeyExA(void) {
    HKEY root = (HKEY)(uintptr_t)ARG(0);
    const char* sub = (const char*)(uintptr_t)ARG(1);
    PHKEY out = (PHKEY)(uintptr_t)ARG(4);
    if (root == HKEY_LOCAL_MACHINE && sub && !_stricmp(sub, MW3_KEY)) {
        LONG r = RegCreateKeyExA(HKEY_CURRENT_USER, MW3_KEY, 0, NULL, 0, KEY_ALL_ACCESS, NULL, out, NULL);
        DWORD opts = MW3_INSTALL_OPTIONS;
        if (r == ERROR_SUCCESS && RegQueryValueExA(*out, "InstallOptions", NULL, NULL, NULL, NULL) != ERROR_SUCCESS)
            RegSetValueExA(*out, "InstallOptions", 0, REG_DWORD, (const BYTE*)&opts, sizeof opts);
        RET(r, 5);
        return;
    }
    RET(RegOpenKeyExA(root, sub, ARG(2), ARG(3), out), 5);
}

static native32_shim_t g_shims[] = {
    { "RegOpenKeyExA", shim_RegOpenKeyExA },
    { "GetLogicalDriveStringsA", shim_GetLogicalDriveStringsA },
    { "GetDriveTypeA", shim_GetDriveTypeA },
    { "GetModuleHandleA", shim_GetModuleHandleA },
    { "GetModuleFileNameA", shim_GetModuleFileNameA },
    { "GetCommandLineA", shim_GetCommandLineA },
    { "ExitProcess", shim_ExitProcess },
};

/* The movies are Indeo 5 (IV50). The game ships the codec, Ir50_32.dll, and
 * its installer registered it; Windows no longer does. Install it for this
 * process only, so ICLocate finds it. */
static void install_indeo(void) {
    HMODULE ir50 = LoadLibraryA("Ir50_32.dll");
    FARPROC proc = ir50 ? GetProcAddress(ir50, "DriverProc") : NULL;
    if (!proc || !ICInstall(ICTYPE_VIDEO, mmioFOURCC('I', 'V', '5', '0'), (LPARAM)proc, NULL, ICINSTALL_FUNCTION))
        fprintf(stderr, "  warning: Indeo 5 codec not installed, the movies will not play\n");
}

/* ------------------------------------------------------------ reports */

recomp_func_t recomp_lookup_manual(uint32_t va) { (void)va; return NULL; }

/* Added after native32's own handler, so callbacks are resolved first and
 * only real faults get here. */
static LONG CALLBACK crash(EXCEPTION_POINTERS* ep) {
    EXCEPTION_RECORD* r = ep->ExceptionRecord;
    if ((r->ExceptionCode & 0xF0000000u) != 0xC0000000u) {
        fprintf(stderr, "[exception] 0x%08lX at 0x%p, in sub_%08X, last native call %s\n",
                r->ExceptionCode, r->ExceptionAddress, g_cur_func, g_cur_import);
        return EXCEPTION_CONTINUE_SEARCH;
    }
    HMODULE in = NULL;
    char mod[MAX_PATH] = "?";
    if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                           (LPCSTR)r->ExceptionAddress, &in))
        GetModuleFileNameA(in, mod, sizeof mod);
    fprintf(stderr, "\n=== fault 0x%08lX at 0x%p (%s+0x%X) ===\n", r->ExceptionCode, r->ExceptionAddress,
            mod, (unsigned)((uintptr_t)r->ExceptionAddress - (uintptr_t)in));
    if (r->ExceptionCode == EXCEPTION_ACCESS_VIOLATION && r->NumberParameters >= 2) {
        ULONG_PTR op = r->ExceptionInformation[0];
        uint32_t at = (uint32_t)r->ExceptionInformation[1];
        fprintf(stderr, "  %s of 0x%08X%s\n", op == 0 ? "read" : op == 1 ? "write" : "execute", at,
                native32_in_guest(at) ? " (inside the guest image)" : at < 0x10000 ? " (null/low)" : "");
    }
    recomp_trace_flush();
    fprintf(stderr, "  in lifted sub_%08X, last native call %s\n", g_cur_func, g_cur_import);
    fprintf(stderr, "  eax=%08X ecx=%08X edx=%08X ebx=%08X esp=%08X ebp=%08X esi=%08X edi=%08X\n",
            g_eax, g_ecx, g_edx, g_ebx, g_esp, g_ebp, g_esi, g_edi);
    native32_dump_icalls(12);
    recomp_dump_trace("fault");
    fflush(stderr);
    TerminateProcess(GetCurrentProcess(), 3);
    return EXCEPTION_CONTINUE_SEARCH;
}

static DWORD WINAPI watchdog(LPVOID unused) {
    (void)unused;
    Sleep(g_watchdog_s * 1000);
    fprintf(stderr, "\n[watchdog] %lu s: in sub_%08X, last native call %s, %u indirect calls\n",
            g_watchdog_s, g_cur_func, g_cur_import, g_icall_count);
    native32_dump_icalls(8);
    fflush(stderr);
    TerminateProcess(GetCurrentProcess(), 4);
    return 0;
}

int main(int argc, char** argv) {
    const char* game = "game";
    int run = 0;
    /* Redirected stderr is block-buffered, and the guest can end the process
     * natively (TerminateProcess, MSVCRT's exit): keep every line. */
    setvbuf(stderr, NULL, _IONBF, 0);
    for (int i = 1; i < argc; i++) {
        int n = recomp_trace_arg(argc, argv, i);
        if (n) { i += n - 1; continue; }
        if (!strcmp(argv[i], "--run")) run = 1;
        else if (!strcmp(argv[i], "--game") && i + 1 < argc) game = argv[++i];
        else if (!strcmp(argv[i], "--watchdog") && i + 1 < argc) g_watchdog_s = strtoul(argv[++i], NULL, 0);
        else if (!strcmp(argv[i], "--native-trace")) native32_trace_native = 1;
        else if (!strcmp(argv[i], "--callbacks")) native32_trace_callbacks = 1;
        else {
            printf("usage: mw3 [--run] [--game DIR] [--watchdog S] [--native-trace] [--callbacks]\n"
                   "  without --run: map and bind Mech3.exe, then stop (no window)\n");
            recomp_trace_help();
            return argv[i][1] == 'h' || argv[i][2] == 'h' ? 0 : 1;
        }
    }
    GetFullPathNameA(game, MAX_PATH - 1, g_game, NULL);
    if (g_game[strlen(g_game) - 1] != '\\') strcat(g_game, "\\");
    _snprintf(g_guest_exe, sizeof g_guest_exe - 1, "%sMech3.exe", g_game);
    _snprintf(g_guest_cmdline, sizeof g_guest_cmdline - 1, "\"%s\"", g_guest_exe);

    /* MFC42.DLL, MSVCP50.DLL and IFORCE2.dll come from the game folder, as
     * they did from the install folder on Windows 98. */
    SetDllDirectoryA(g_game);
    native32_init();
    install_indeo();
    AddVectoredExceptionHandler(0, crash);
    printf("MechWarrior 3 recomp host\n  lifted functions in dispatch: %u\n", recomp_dispatch_count);
    uint32_t span = native32_map(g_guest_exe, MW3_BASE);
    if (!span) { fprintf(stderr, "cannot map %s at 0x%08X\n", g_guest_exe, MW3_BASE); return 1; }
    printf("  mapped Mech3.exe: 0x%08X-0x%08X\n", MW3_BASE, MW3_BASE + span);
    int unresolved = native32_bind(MW3_BASE, g_shims, (int)(sizeof g_shims / sizeof g_shims[0]));
    printf("  imports bound, %d unresolved\n", unresolved);
    if (unresolved) return 1;
    if (!patch_native_import("MFC42.DLL", "GetModuleFileNameA", native_GetModuleFileNameA))
        fprintf(stderr, "  warning: MFC42.DLL GetModuleFileNameA not patched\n");
    if (!run) {
        printf("\n(dry run: image mapped and bound; --run enters 0x%08X)\n", mw3_entry_va);
        return 0;
    }
    /* The CRT startup takes WinMain's lpCmdLine from MSVCRT's _acmdln, not
     * from GetCommandLineA: give it the guest's, not this host's flags. */
    char** acmdln = (char**)GetProcAddress(GetModuleHandleA("MSVCRT.dll"), "_acmdln");
    if (acmdln) *acmdln = g_guest_cmdline;
    /* The game opens zbd\ and video\ relative to its own folder. */
    if (!SetCurrentDirectoryA(g_game)) { fprintf(stderr, "cannot enter %s\n", g_game); return 1; }
    if (g_watchdog_s) CloseHandle(CreateThread(NULL, 0, watchdog, NULL, 0, NULL));
    printf("  entering 0x%08X\n\n", mw3_entry_va);
    fflush(stdout);
    native32_call_guest(mw3_entry_va, 0, NULL);
    printf("\nentry returned eax=%08X\n", g_eax);
    return (int)g_eax;
}
