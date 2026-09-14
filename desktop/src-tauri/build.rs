use std::fs;

fn main() {
    let version = read_sidecar_version();
    println!("cargo:rustc-env=SIDECAR_VERSION={version}");
    println!("cargo:rerun-if-changed=../../cli_tool/_version.py");
    tauri_build::build()
}

fn read_sidecar_version() -> String {
    let Ok(content) = fs::read_to_string("../../cli_tool/_version.py") else {
        return "0.0.0".into();
    };
    for line in content.lines() {
        let line = line.trim();
        if !line.starts_with("__version__") {
            continue;
        }
        if let Some(first) = line.find('\'') {
            if let Some(rel) = line[first + 1..].find('\'') {
                return line[first + 1..first + 1 + rel].to_string();
            }
        }
    }
    "0.0.0".into()
}
