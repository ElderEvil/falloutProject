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

#[cfg(target_os = "linux")]
async fn tray_host_available(builder: zbus::connection::Builder<'_>) -> zbus::Result<bool> {
    let connection = builder
        .method_timeout(std::time::Duration::from_secs(1))
        .build()
        .await?;
    let watcher = zbus::Proxy::new(
        &connection,
        "org.kde.StatusNotifierWatcher",
        "/StatusNotifierWatcher",
        "org.kde.StatusNotifierWatcher",
    )
    .await?;
    watcher.get_property("IsStatusNotifierHostRegistered").await
}

#[cfg(desktop)]
async fn close_main_window(window: tauri::Window) {
    #[cfg(target_os = "linux")]
    let host_available = match zbus::connection::Builder::session() {
        Ok(builder) => tray_host_available(builder).await.unwrap_or(false),
        Err(_) => false,
    };
    #[cfg(not(target_os = "linux"))]
    let host_available = true;

    if !host_available {
        window.app_handle().exit(0);
    } else if let Err(error) = window.hide() {
        eprintln!("Unable to hide desktop window; closing instead: {error}");
        window.app_handle().exit(0);
    }
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
                api.prevent_close();
                tauri::async_runtime::spawn(close_main_window(window.clone()));
            }
        });
    builder
        .run(tauri::generate_context!())
        .expect("error while running Fallout Shelter");
}

#[cfg(all(test, target_os = "linux"))]
mod tests {
    use super::tray_host_available;
    use std::{
        io::{BufRead, BufReader},
        process::{Child, Command, Stdio},
        sync::{
            Arc,
            atomic::{AtomicBool, Ordering},
        },
    };

    struct PrivateBus(Child);

    impl Drop for PrivateBus {
        fn drop(&mut self) {
            let _ = self.0.kill();
            let _ = self.0.wait();
        }
    }

    struct Watcher(Arc<AtomicBool>);

    #[zbus::interface(name = "org.kde.StatusNotifierWatcher")]
    impl Watcher {
        #[zbus(property)]
        fn is_status_notifier_host_registered(&self) -> bool {
            self.0.load(Ordering::SeqCst)
        }
    }

    #[test]
    fn hide_requires_a_registered_tray_host() {
        let mut bus = PrivateBus(
            Command::new("dbus-daemon")
                .args(["--session", "--nofork", "--print-address=1"])
                .stdout(Stdio::piped())
                .spawn()
                .expect("dbus-daemon is required for the Linux tray regression"),
        );
        let mut address = String::new();
        BufReader::new(bus.0.stdout.take().unwrap())
            .read_line(&mut address)
            .unwrap();

        tauri::async_runtime::block_on(async {
            let query = || zbus::connection::Builder::address(address.trim()).unwrap();
            assert!(!tray_host_available(query()).await.unwrap_or(false));
            let registered = Arc::new(AtomicBool::new(false));
            let _watcher = query()
                .name("org.kde.StatusNotifierWatcher")
                .unwrap()
                .serve_at("/StatusNotifierWatcher", Watcher(registered.clone()))
                .unwrap()
                .build()
                .await
                .unwrap();
            assert!(!tray_host_available(query()).await.unwrap());
            registered.store(true, Ordering::SeqCst);
            assert!(tray_host_available(query()).await.unwrap());
        });
    }
}
