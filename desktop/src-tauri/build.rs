use std::fs;

const MIN_VERSION: &str = "3.10.0";

fn main() {
    let version = read_devo_cli_version();
    println!("cargo:rustc-env=DEVO_CLI_VERSION={version}");
    println!("cargo:rustc-env=DEVO_CLI_MIN_VERSION={MIN_VERSION}");
    println!("cargo:rerun-if-changed=../../cli_tool/_version.py");
    tauri_build::build()
}

fn read_devo_cli_version() -> String {
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
