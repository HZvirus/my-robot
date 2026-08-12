/**
 * Boot the Python AI service alongside the JS apps.
 * Usage: pnpm dev:all
 */
import { spawn } from 'node:child_process'

const services = [
  { name: 'ai-service', cmd: 'uvicorn', args: ['app.main:app', '--reload', '--port', '8000'], cwd: 'apps/ai-service' },
  { name: 'h5-app1', cmd: 'pnpm', args: ['dev'], cwd: 'apps/h5-app1' },
  { name: 'h5-app2', cmd: 'pnpm', args: ['dev'], cwd: 'apps/h5-app2' }
]

for (const svc of services) {
  const child = spawn(svc.cmd, svc.args, { cwd: svc.cwd, shell: true, stdio: 'inherit' })
  child.on('exit', (code) => console.log(`[${svc.name}] exited with ${code}`))
}
