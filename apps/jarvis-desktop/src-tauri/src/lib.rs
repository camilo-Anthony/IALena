use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;
use tauri::{AppHandle, Manager};

static SIDEBAR_OPEN: AtomicBool = AtomicBool::new(false);
static IS_ORB_VIEW: AtomicBool = AtomicBool::new(true);

#[cfg(windows)]
#[repr(C)]
struct POINT {
    x: i32,
    y: i32,
}

#[cfg(windows)]
extern "system" {
    fn GetCursorPos(lp_point: *mut POINT) -> i32;
    fn GetSystemMetrics(nindex: i32) -> i32;
}

#[tauri::command]
fn get_cursor_position(app: AppHandle) -> Option<(f64, f64)> {
    #[cfg(windows)]
    unsafe {
        let mut pt = POINT { x: 0, y: 0 };
        if GetCursorPos(&mut pt) != 0 {
            return Some((pt.x as f64, pt.y as f64));
        }
    }

    if let Some(window) = app.get_webview_window("main") {
        if let Ok(pos) = window.cursor_position() {
            return Some((pos.x, pos.y));
        }
    }
    None
}

#[tauri::command]
fn set_sidebar_open(open: bool) {
    SIDEBAR_OPEN.store(open, Ordering::Relaxed);
}

#[tauri::command]
fn set_active_view_state(view: String) {
    IS_ORB_VIEW.store(view == "orb", Ordering::Relaxed);
}

#[tauri::command]
fn launch_hermes_app() -> Result<(), String> {
    #[cfg(windows)]
    {
        use std::process::Command;
        Command::new("cmd")
            .args(&["/c", "start", "Hermes Desktop", "/Min", "cmd", "/c", "cd Hermes-Agent\\apps\\desktop && npm run dev"])
            .spawn()
            .map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
fn set_click_through(app: AppHandle, ignore: bool) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("main") {
        window.set_ignore_cursor_events(ignore).map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|app| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.set_decorations(false);
                let _ = window.set_shadow(false);

                // Dimensionar la ventana cubriendo toda la pantalla física (incluyendo barra de tareas)
                // sin activar el modo fullscreen nativo de Windows (que crea el cabecero gris)
                if let Ok(Some(monitor)) = window.current_monitor() {
                    let size = monitor.size();
                    let _ = window.set_position(tauri::Position::Physical(tauri::PhysicalPosition { x: 0, y: 0 }));
                    let _ = window.set_size(tauri::Size::Physical(*size));
                }
            }

            // Hilo de control inteligente de click-through:
            // Permite al usuario usar Windows normalmente (click-through activo)
            // y solo activa la ventana cuando el cursor pasa sobre el botón lateral
            // o cuando el menú/panel está abierto.
            let handle = app.handle().clone();
            std::thread::spawn(move || {
                let mut last_ignore = false;
                loop {
                    std::thread::sleep(Duration::from_millis(25));

                    let is_orb = IS_ORB_VIEW.load(Ordering::Relaxed);
                    let is_open = SIDEBAR_OPEN.load(Ordering::Relaxed);

                    if !is_orb || is_open {
                        // En vista panel/hermes o con menú abierto: siempre interactivo
                        if last_ignore {
                            if let Some(window) = handle.get_webview_window("main") {
                                let _ = window.set_ignore_cursor_events(false);
                            }
                            last_ignore = false;
                        }
                        continue;
                    }

                    // En vista Orbe con menú cerrado: probar hit-test en el notch lateral
                    #[cfg(windows)]
                    unsafe {
                        let mut pt = POINT { x: 0, y: 0 };
                        if GetCursorPos(&mut pt) != 0 {
                            let screen_w = GetSystemMetrics(0); // SM_CXSCREEN
                            let screen_h = GetSystemMetrics(1); // SM_CYSCREEN

                            // Zona del botón lateral derecho: últimos 50px de la pantalla, centrado vertical ±80px
                            let in_notch = pt.x >= (screen_w - 50) && (pt.y - screen_h / 2).abs() <= 80;

                            let should_ignore = !in_notch;
                            if should_ignore != last_ignore {
                                if let Some(window) = handle.get_webview_window("main") {
                                    let _ = window.set_ignore_cursor_events(should_ignore);
                                }
                                last_ignore = should_ignore;
                            }
                        }
                    }
                }
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            get_cursor_position,
            set_click_through,
            set_sidebar_open,
            set_active_view_state,
            launch_hermes_app
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
