#!/usr/bin/env node
import { execSync } from 'node:child_process';

const isWin = process.platform === 'win32';

function run(cmd) {
  try {
    execSync(cmd, { stdio: 'ignore' });
  } catch {
    /* ignore */
  }
}

if (isWin) {
  run('powershell -ExecutionPolicy Bypass -File kill-zombies.ps1');
} else {
  run('bash kill-zombies.sh');
}
