mod utils;

#[cfg_attr(feature = "desktop", tauri::command)]
pub fn read_file(path: String) -> Result<String, String> {
    utils::read_document(&path)
}

#[cfg(feature = "desktop")]
pub fn register<R: tauri::Runtime>(builder: tauri::Builder<R>) -> tauri::Builder<R> {
    builder.invoke_handler(tauri::generate_handler![read_file])
}
