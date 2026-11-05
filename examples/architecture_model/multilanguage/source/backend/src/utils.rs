pub fn read_document(path: &str) -> Result<String, String> {
    std::fs::read_to_string(path).map_err(|error| error.to_string())
}
