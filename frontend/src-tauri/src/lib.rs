#[cfg(desktop)]
use tauri::{
    Manager,
    menu::{Menu, MenuItem},
    tray::TrayIconBuilder,
};
#[cfg(desktop)]
use tauri_plugin_window_state::{AppHandleExt, StateFlags};

#[cfg(desktop)]
struct DesktopTray;

#[cfg(desktop)]
fn window_state_flags() -> StateFlags {
    // Hidden-to-tray and minimized state must not make the next launch invisible.
    StateFlags::SIZE | StateFlags::POSITION | StateFlags::MAXIMIZED
}

#[cfg(desktop)]
fn show_main_window(app: &tauri::AppHandle) -> tauri::Result<()> {
    if let Some(window) = app.get_webview_window("main") {
        window.unminimize()?;
        window.show()?;
        window.set_focus()?;
    }
    Ok(())
}

#[cfg(desktop)]
fn setup_desktop(app: &mut tauri::App) -> Result<(), Box<dyn std::error::Error>> {
    let show = MenuItem::with_id(app, "show", "Show Fallout Shelter", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&show, &quit])?;
    let icon = app
        .default_window_icon()
        .ok_or_else(|| std::io::Error::other("Missing application icon"))?;
    let tray = TrayIconBuilder::with_id("fallout")
        .icon(icon.clone())
        .tooltip("Fallout Shelter")
        .menu(&menu)
        .show_menu_on_left_click(true)
        .on_menu_event(|app, event| match event.id.as_ref() {
            "show" => {
                if let Err(error) = show_main_window(app) {
                    eprintln!("Unable to restore the desktop window: {error}");
                }
            }
            "quit" => app.exit(0),
            _ => {}
        })
        .build(app);
    match tray {
        Ok(_) => {
            app.manage(DesktopTray);
        }
        Err(error) => eprintln!("Unable to create tray; closing the window will quit: {error}"),
    }
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_opener::init());
    #[cfg(desktop)]
    let builder = builder
        .plugin(
            tauri_plugin_window_state::Builder::default()
                .with_state_flags(window_state_flags())
                .build(),
        )
        .setup(setup_desktop)
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                if window.label() != "main"
                    || window.app_handle().try_state::<DesktopTray>().is_none()
                {
                    return;
                }
                if let Err(error) = window.app_handle().save_window_state(window_state_flags()) {
                    eprintln!("Unable to save desktop window state: {error}");
                }
                match window.hide() {
                    Ok(()) => api.prevent_close(),
                    Err(error) => {
                        eprintln!("Unable to hide desktop window; closing instead: {error}")
                    }
                }
            }
        });
    builder
        .run(tauri::generate_context!())
        .expect("error while running Fallout Shelter");
}
