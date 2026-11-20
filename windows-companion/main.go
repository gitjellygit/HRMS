//go:build windows

// JellyGit Activity Companion v0.6: automatic tray monitoring with reason-gated exit.
// Records aggregate active/idle seconds and foreground application name, never keys/screens/URLs.
package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

var (
	user32                        = syscall.NewLazyDLL("user32.dll")
	kernel32                      = syscall.NewLazyDLL("kernel32.dll")
	shell32                       = syscall.NewLazyDLL("shell32.dll")
	procRegisterClassEx           = user32.NewProc("RegisterClassExW")
	procCreateWindowEx            = user32.NewProc("CreateWindowExW")
	procDefWindowProc             = user32.NewProc("DefWindowProcW")
	procGetMessage                = user32.NewProc("GetMessageW")
	procTranslateMessage          = user32.NewProc("TranslateMessage")
	procDispatchMessage           = user32.NewProc("DispatchMessageW")
	procPostQuitMessage           = user32.NewProc("PostQuitMessage")
	procDestroyWindow             = user32.NewProc("DestroyWindow")
	procSetWindowText             = user32.NewProc("SetWindowTextW")
	procGetWindowText             = user32.NewProc("GetWindowTextW")
	procShowWindow                = user32.NewProc("ShowWindow")
	procSetForegroundWindow       = user32.NewProc("SetForegroundWindow")
	procSetTimer                  = user32.NewProc("SetTimer")
	procKillTimer                 = user32.NewProc("KillTimer")
	procGetLastInputInfo          = user32.NewProc("GetLastInputInfo")
	procGetForegroundWindow       = user32.NewProc("GetForegroundWindow")
	procGetWindowThreadProcessId  = user32.NewProc("GetWindowThreadProcessId")
	procMessageBox                = user32.NewProc("MessageBoxW")
	procLoadIcon                  = user32.NewProc("LoadIconW")
	procGetModuleHandle           = kernel32.NewProc("GetModuleHandleW")
	procGetTickCount              = kernel32.NewProc("GetTickCount")
	procOpenProcess               = kernel32.NewProc("OpenProcess")
	procQueryFullProcessImageName = kernel32.NewProc("QueryFullProcessImageNameW")
	procCloseHandle               = kernel32.NewProc("CloseHandle")
	procShellNotifyIcon           = shell32.NewProc("Shell_NotifyIconW")
)

const (
	wmCreate            = 0x0001
	wmDestroy           = 0x0002
	wmCommand           = 0x0111
	wmTimer             = 0x0113
	wmClose             = 0x0010
	wmTray              = 0x8001
	wmLButtonUp         = 0x0202
	wmRButtonUp         = 0x0205
	wsOverlappedWindow  = 0x00CF0000
	wsVisible           = 0x10000000
	wsChild             = 0x40000000
	wsBorder            = 0x00800000
	esMultiline         = 0x0004
	btnExit             = 1002
	btnConfirm          = 1003
	btnCancel           = 1004
	swHide              = 0
	swShow              = 5
	nifMessage          = 1
	nifIcon             = 2
	nifTip              = 4
	nimAdd              = 0
	nimModify           = 1
	nimDelete           = 2
	processQueryLimited = 0x1000
)

type point struct{ X, Y int32 }
type msg struct {
	Hwnd           uintptr
	Message        uint32
	WParam, LParam uintptr
	Time           uint32
	Pt             point
	LPrivate       uint32
}
type wndClass struct {
	CbSize                                                             uint32
	Style                                                              uint32
	WndProc                                                            uintptr
	ClsExtra, WndExtra                                                 int32
	Instance, Icon, Cursor, Background, MenuName, ClassName, IconSmall uintptr
}
type lastInput struct {
	CbSize uint32
	DwTime uint32
}
type notifyIcon struct {
	CbSize          uint32
	Hwnd            uintptr
	UID             uint32
	Flags           uint32
	CallbackMessage uint32
	HIcon           uintptr
	Tip             [128]uint16
	State           uint32
	StateMask       uint32
	Info            [256]uint16
	Version         uint32
	InfoTitle       [64]uint16
	InfoFlags       uint32
	Guid            [16]byte
	BalloonIcon     uintptr
}
type config struct {
	APIURL         string `json:"api_url"`
	DeviceToken    string `json:"device_token"`
	EmployeeID     int    `json:"employee_id,omitempty"`
	InvitationCode string `json:"invitation_code,omitempty"`
}
type payload struct {
	State         string           `json:"state"`
	ActiveSeconds int64            `json:"active_seconds"`
	IdleSeconds   int64            `json:"idle_seconds"`
	ExitReason    string           `json:"exit_reason,omitempty"`
	Apps          map[string]int64 `json:"apps"`
}

var hwnd, statusText, reasonText, reasonEdit, confirmButton, cancelButton, exitButton uintptr
var active, quitPrompt, exiting bool
var activeSecs, idleSecs int64
var appSecs = map[string]int64{}
var currentDate = time.Now().Format("2006-01-02")
var lastTick = time.Now()
var lastBeat = time.Time{}

const defaultAPIURL = "https://api-hrms.jellygit.com"

var cfg config
var registrationReady bool
var registrationBusy bool
var registrationResults = make(chan error, 1)
var nextRegistration time.Time
var lastStatusAssigned bool

var icon notifyIcon
var client = &http.Client{Timeout: 6 * time.Second}
var assignmentResult = make(chan bool, 1)
var assignmentPolling bool
var lastAssignmentCheck time.Time

func ptr(s string) uintptr        { p, _ := syscall.UTF16PtrFromString(s); return uintptr(unsafe.Pointer(p)) }
func setText(h uintptr, s string) { procSetWindowText.Call(h, ptr(s)) }
func getText(h uintptr) string {
	b := make([]uint16, 1100)
	procGetWindowText.Call(h, uintptr(unsafe.Pointer(&b[0])), uintptr(len(b)))
	return syscall.UTF16ToString(b)
}
func dataDir() string {
	root := os.Getenv("LOCALAPPDATA")
	if root == "" {
		root = os.TempDir()
	}
	return filepath.Join(root, "JellyGitActivity")
}
func loadConfig() error {
	cfg.APIURL = defaultAPIURL
	raw, err := os.ReadFile(filepath.Join(dataDir(), "config.json"))
	if err == nil {
		if err := json.Unmarshal(raw, &cfg); err != nil {
			return fmt.Errorf("Saved device settings are invalid: %w", err)
		}
	} else if !errors.Is(err, os.ErrNotExist) {
		return fmt.Errorf("Cannot read device settings: %w", err)
	}
	// Do not redirect the companion to an arbitrary server.
	if strings.TrimRight(cfg.APIURL, "/") != defaultAPIURL {
		return fmt.Errorf("Device API host is not trusted")
	}
	if cfg.DeviceToken != "" {
		registrationReady = true
	}
	return nil
}
func saveConfig() error {
	if err := os.MkdirAll(dataDir(), 0700); err != nil {
		return err
	}
	content, err := json.MarshalIndent(cfg, "", "  ")
	if err != nil {
		return err
	}
	name := filepath.Join(dataDir(), "config.json")
	temp, err := os.CreateTemp(dataDir(), "device-*.tmp")
	if err != nil {
		return err
	}
	defer os.Remove(temp.Name())
	if _, err = temp.Write(content); err != nil {
		temp.Close()
		return err
	}
	if err = temp.Close(); err != nil {
		return err
	}
	return os.Rename(temp.Name(), name)
}
func registerDevice() error {
	// A server token may already exist if the earlier save failed; avoid
	// creating multiple pending devices while retrying local storage.
	if cfg.DeviceToken != "" {
		return saveConfig()
	}
	name, err := os.Hostname()
	if err != nil || len(name) < 3 {
		name = "Windows workstation"
	}
	if len(name) > 120 {
		name = name[:120]
	}
	b, _ := json.Marshal(map[string]string{"device_label": name})
	req, err := http.NewRequest("POST", defaultAPIURL+"/activity-agent/register-auto", bytes.NewReader(b))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	raw, _ := io.ReadAll(io.LimitReader(resp.Body, 4096))
	if resp.StatusCode != 201 {
		return fmt.Errorf("Device registration HTTP %d: %s", resp.StatusCode, string(raw))
	}
	var result struct {
		Token string `json:"token"`
	}
	if err := json.Unmarshal(raw, &result); err != nil {
		return err
	}
	if len(result.Token) < 32 {
		return fmt.Errorf("HRMS returned an invalid device credential")
	}
	cfg.DeviceToken = result.Token
	return saveConfig()
}
func registerAsync() {
	err := registerDevice()
	select {
	case registrationResults <- err:
	default:
	}
}
func checkAssignmentAsync() {
	req, err := http.NewRequest("GET", strings.TrimRight(cfg.APIURL, "/")+"/activity-agent/status", nil)
	if err != nil {
		select {
		case assignmentResult <- false:
		default:
		}
		return
	}
	req.Header.Set("Authorization", "Bearer "+cfg.DeviceToken)
	resp, err := client.Do(req)
	approved := false
	if err == nil {
		var result struct {
			Assigned bool `json:"assigned"`
		}
		if resp.StatusCode == 200 {
			_ = json.NewDecoder(io.LimitReader(resp.Body, 4096)).Decode(&result)
			approved = result.Assigned
		}
		resp.Body.Close()
	}
	select {
	case assignmentResult <- approved:
	default:
	}
}
func sendBeat(state, reason string) error {
	b, _ := json.Marshal(payload{State: state, ActiveSeconds: activeSecs, IdleSeconds: idleSecs, ExitReason: reason, Apps: copyAppSecs()})
	url := strings.TrimRight(cfg.APIURL, "/") + "/activity-agent/heartbeat"
	req, err := http.NewRequest("POST", url, bytes.NewReader(b))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+cfg.DeviceToken)
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	io.Copy(io.Discard, io.LimitReader(resp.Body, 4096))
	if resp.StatusCode != 200 {
		return fmt.Errorf("HRMS heartbeat returned HTTP %d", resp.StatusCode)
	}
	return nil
}
func copyAppSecs() map[string]int64 {
	out := make(map[string]int64, len(appSecs))
	for k, v := range appSecs {
		out[k] = v
	}
	return out
}
func foregroundApp() string {
	w, _, _ := procGetForegroundWindow.Call()
	if w == 0 {
		return "unknown"
	}
	var pid uint32
	procGetWindowThreadProcessId.Call(w, uintptr(unsafe.Pointer(&pid)))
	if pid == 0 {
		return "unknown"
	}
	h, _, _ := procOpenProcess.Call(processQueryLimited, 0, uintptr(pid))
	if h == 0 {
		return "protected"
	}
	defer procCloseHandle.Call(h)
	b := make([]uint16, 1024)
	length := uint32(len(b))
	ok, _, _ := procQueryFullProcessImageName.Call(h, 0, uintptr(unsafe.Pointer(&b[0])), uintptr(unsafe.Pointer(&length)))
	if ok == 0 {
		return "protected"
	}
	return strings.TrimSuffix(strings.ToLower(filepath.Base(syscall.UTF16ToString(b[:length]))), ".exe")
}
func idleDuration() time.Duration {
	p := lastInput{CbSize: uint32(unsafe.Sizeof(lastInput{}))}
	ok, _, _ := procGetLastInputInfo.Call(uintptr(unsafe.Pointer(&p)))
	if ok == 0 {
		return 0
	}
	tick, _, _ := procGetTickCount.Call()
	return time.Duration(uint32(tick)-p.DwTime) * time.Millisecond
}
func makeControl(class, title string, x, y, w, h int32, id int, style uint32) uintptr {
	handle, _, _ := procCreateWindowEx.Call(0, ptr(class), ptr(title), uintptr(wsChild|wsVisible|style), uintptr(x), uintptr(y), uintptr(w), uintptr(h), hwnd, uintptr(id), 0, 0)
	return handle
}
func dialog(s string) { procMessageBox.Call(hwnd, ptr(s), ptr("JellyGit Activity Companion"), 0x40) }
func configureExitUI(show bool) {
	mode := swHide
	if show {
		mode = swShow
	}
	for _, h := range []uintptr{reasonText, reasonEdit, confirmButton, cancelButton} {
		procShowWindow.Call(h, uintptr(mode))
	}
	procShowWindow.Call(exitButton, uintptr(swShow))
	quitPrompt = show
}
func showWindow() { procShowWindow.Call(hwnd, swShow); procSetForegroundWindow.Call(hwnd) }
func iconChange(added bool) {
	operation := uintptr(nimAdd)
	if !added {
		operation = nimDelete
	}
	procShellNotifyIcon.Call(operation, uintptr(unsafe.Pointer(&icon)))
}
func updateTrayTip(message string) {
	for i := range icon.Tip {
		icon.Tip[i] = 0
	}
	copy(icon.Tip[:], syscall.StringToUTF16(message))
	procShellNotifyIcon.Call(nimModify, uintptr(unsafe.Pointer(&icon)))
}
func tick() {
	now := time.Now()
	if !registrationReady {
		select {
		case err := <-registrationResults:
			registrationBusy = false
			if err != nil {
				setText(statusText, "Cannot contact HRMS yet. Waiting and retrying registration.\r\n"+err.Error())
				updateTrayTip("JellyGit Activity Companion - Registration retry")
			} else {
				registrationReady = true
				setText(statusText, "Laptop registered. Waiting for HR to assign and approve monitoring.\r\nNo activity data is being collected.")
				updateTrayTip("JellyGit Activity Companion - Pending HR assignment")
			}
		default:
		}
		if !registrationReady && !registrationBusy && !now.Before(nextRegistration) {
			nextRegistration = now.Add(30 * time.Second)
			registrationBusy = true
			go registerAsync()
		}
		return
	}
	select {
	case assigned := <-assignmentResult:
		assignmentPolling = false
		if !assigned && active {
			active = false
			setText(statusText, "Monitoring paused. HRMS assignment unavailable or revoked.")
			updateTrayTip("JellyGit Activity Companion - Not assigned")
		}
		if assigned && !active {
			active = true
			lastTick = now
			lastBeat = time.Time{}
			setText(statusText, "Assigned by HR. Activity reporting is now active.\r\nTracks aggregate active/idle time and foreground apps; no screenshots, typing or URLs.")
			updateTrayTip("JellyGit Activity Companion - Monitoring")
		}
	default:
	}
	if !assignmentPolling && now.Sub(lastAssignmentCheck) >= 30*time.Second {
		lastAssignmentCheck = now
		assignmentPolling = true
		go checkAssignmentAsync()
	}
	if !active {
		return
	}
	if now.Format("2006-01-02") != currentDate {
		currentDate = now.Format("2006-01-02")
		activeSecs = 0
		idleSecs = 0
		appSecs = map[string]int64{}
	}
	elapsed := now.Sub(lastTick)
	lastTick = now
	if active && elapsed > 0 && elapsed < 10*time.Second {
		seconds := int64(elapsed.Seconds())
		if seconds < 1 {
			seconds = 1
		}
		if idleDuration() >= 5*time.Minute {
			idleSecs += seconds
		} else {
			activeSecs += seconds
			name := foregroundApp()
			if len(name) > 60 {
				name = name[:60]
			}
			if _, ok := appSecs[name]; ok || len(appSecs) < 30 {
				appSecs[name] += seconds
			}
		}
	}
	if active && time.Since(lastBeat) >= 30*time.Second {
		lastBeat = now
		// Copy counters into immutable payload before background I/O.
		snapshot := payload{State: "monitoring", ActiveSeconds: activeSecs, IdleSeconds: idleSecs, Apps: copyAppSecs()}
		go func(p payload) {
			b, _ := json.Marshal(p)
			req, err := http.NewRequest("POST", strings.TrimRight(cfg.APIURL, "/")+"/activity-agent/heartbeat", bytes.NewReader(b))
			if err != nil {
				return
			}
			req.Header.Set("Content-Type", "application/json")
			req.Header.Set("Authorization", "Bearer "+cfg.DeviceToken)
			resp, err := client.Do(req)
			if err == nil {
				io.Copy(io.Discard, io.LimitReader(resp.Body, 1024))
				resp.Body.Close()
			}
		}(snapshot)
	}
	if active {
		setText(statusText, "Monitoring active. Running in the Windows notification area.\r\nTracks active/idle time and foreground applications; no screenshots, typing, or URLs.")
	}
}
func stopWithReason() {
	reason := strings.TrimSpace(getText(reasonEdit))
	if len([]rune(reason)) < 10 {
		dialog("Provide a reason of at least 10 characters before exiting.")
		return
	}
	// Stop collection immediately, before attempting to transmit status.
	wasMonitoring := active
	active = false
	if wasMonitoring {
		if err := sendBeat("stopped", reason); err != nil {
			// Offline state will be inferred by the HRMS heartbeat timeout.
			_ = os.MkdirAll(dataDir(), 0700)
			_ = os.WriteFile(filepath.Join(dataDir(), "last-exit-reason.txt"), []byte(time.Now().Format(time.RFC3339)+"\n"+reason+"\n"), 0600)
			dialog("Monitoring has stopped. HRMS could not be contacted; the dashboard will show Offline after heartbeat timeout.\n" + err.Error())
		}
	}
	exiting = true
	procDestroyWindow.Call(hwnd)
}
func windowProc(h uintptr, message uint32, wp, lp uintptr) uintptr {
	switch message {
	case wmCreate:
		hwnd = h
		makeControl("STATIC", "JellyGit Activity Companion  |  Activity status", 18, 16, 560, 24, 0, 0)
		statusText = makeControl("STATIC", "Initializing device connection...", 18, 50, 560, 65, 0, 0)
		exitButton = makeControl("BUTTON", "Exit companion", 18, 125, 170, 40, btnExit, 0)
		reasonText = makeControl("STATIC", "Reason for exit (required, minimum 10 characters):", 18, 190, 540, 24, 0, 0)
		reasonEdit = makeControl("EDIT", "", 18, 221, 535, 58, 0, wsBorder|esMultiline)
		confirmButton = makeControl("BUTTON", "Confirm exit", 18, 300, 170, 38, btnConfirm, 0)
		cancelButton = makeControl("BUTTON", "Cancel", 200, 300, 170, 38, btnCancel, 0)
		configureExitUI(false)
		icon = notifyIcon{CbSize: uint32(unsafe.Sizeof(notifyIcon{})), Hwnd: hwnd, UID: 1, Flags: nifMessage | nifIcon | nifTip, CallbackMessage: wmTray}
		icon.HIcon, _, _ = procLoadIcon.Call(0, 32512) // standard application icon
		copy(icon.Tip[:], syscall.StringToUTF16("JellyGit Activity Companion - Monitoring"))
		iconChange(true)
		// A missing or invalid enrollment cannot collect activity. Provide a clear
		// setup error instead of silently running an unconfigured background app.
		if err := loadConfig(); err != nil {
			dialog(err.Error())
			exiting = true
			procDestroyWindow.Call(hwnd)
			return 0
		}
		active = false // Never collect activity until HR assignment is confirmed.
		lastAssignmentCheck = time.Time{}
		setText(statusText, "Registering company laptop with HRMS. No activity collected before HR assignment.")
		updateTrayTip("JellyGit Activity Companion - Pending assignment")
		procSetTimer.Call(hwnd, 1, 1000, 0)
		tick() // begin assignment checks; no activity collection while pending
		return 0
	case wmTray:
		if lp == wmLButtonUp || lp == wmRButtonUp {
			showWindow()
		}
		return 0
	case wmCommand:
		switch int(wp & 0xffff) {
		case btnExit:
			configureExitUI(true)
		case btnCancel:
			configureExitUI(false)
		case btnConfirm:
			stopWithReason()
		}
		return 0
	case wmTimer:
		tick()
		return 0
	case wmClose:
		showWindow()
		configureExitUI(true)
		return 0
	case wmDestroy:
		if !exiting {
			active = false
		}
		iconChange(false)
		procKillTimer.Call(h, 1)
		procPostQuitMessage.Call(0)
		return 0
	}
	result, _, _ := procDefWindowProc.Call(h, uintptr(message), wp, lp)
	return result
}
func main() {
	instance, _, _ := procGetModuleHandle.Call(0)
	callback := syscall.NewCallback(windowProc)
	cls := wndClass{CbSize: uint32(unsafe.Sizeof(wndClass{})), WndProc: callback, Instance: instance, Background: 6, ClassName: ptr("JellyGitActivityCompanionWindowV2")}
	atom, _, e := procRegisterClassEx.Call(uintptr(unsafe.Pointer(&cls)))
	if atom == 0 {
		panic(e)
	}
	win, _, e := procCreateWindowEx.Call(0, cls.ClassName, ptr("JellyGit Activity Companion v0.6"), wsOverlappedWindow, 300, 150, 590, 420, 0, 0, instance, 0)
	if win == 0 {
		panic(e)
	}
	var m msg
	for {
		v, _, _ := procGetMessage.Call(uintptr(unsafe.Pointer(&m)), 0, 0, 0)
		if int32(v) <= 0 {
			break
		}
		procTranslateMessage.Call(uintptr(unsafe.Pointer(&m)))
		procDispatchMessage.Call(uintptr(unsafe.Pointer(&m)))
	}
}