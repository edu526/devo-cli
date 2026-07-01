// ponytail: embeds the UAC manifest into the helper binary so Windows shows
// "Devo" in the consent prompt (assemblyIdentity name) and auto-elevates
// the process to admin (requestedExecutionLevel = requireAdministrator).
// Without this, ShellExecuteExW+runas would prompt for "cmd.exe" instead.
fn main() {
    let _ = embed_resource::compile("helper.rc", embed_resource::NONE);
}
