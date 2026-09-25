/**
 * omniline statusline footer for Pi.
 *
 * Pi has no harness-invoked statusline-command hook -- its footer is an
 * in-process callback (`ctx.ui.setFooter()`), not something Pi calls out
 * to with JSON on stdin the way Claude Code and antigravity-cli do. So
 * this extension does the invoking itself: it gathers what it can see
 * in-process and pipes it to bin/pi-statusline on stdin, the same
 * JSON-on-stdin contract every other omniline adapter uses. Rendering
 * must stay synchronous, so refreshes run on a timer and on session
 * events, updating a cached line that render() just returns.
 */
import { spawn } from "node:child_process";
import { homedir } from "node:os";
import { join } from "node:path";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { truncateToWidth } from "@earendil-works/pi-tui";

// Hardcoded, not resolved from import.meta.url: this extension is loaded
// through a symlink in ~/.pi/agent/extensions/, and Pi's jiti-based loader
// does not reliably resolve import.meta.url through that symlink back to
// this file's real location -- a relative path silently pointed at a
// nonexistent file and failed every refresh with no visible error. This
// matches the same fixed location every other Herdr-integrated CLI's
// statusline entrypoint hardcodes (see ~/.claude/statusline-command.sh).
const STATUSLINE_BIN = join(homedir(), "dev", "tools", "omniline", "bin", "pi-statusline");
const REFRESH_MS = 2000;

function sessionTokens(ctx: ExtensionContext): { input: number; output: number; cost: number } {
	let input = 0;
	let output = 0;
	let cost = 0;
	for (const entry of ctx.sessionManager.getBranch()) {
		if (entry.type !== "message" || entry.message.role !== "assistant") continue;
		const usage = (
			entry.message as { usage?: { input?: number; output?: number; cost?: { total?: number } } }
		).usage;
		input += usage?.input ?? 0;
		output += usage?.output ?? 0;
		cost += usage?.cost?.total ?? 0;
	}
	return { input, output, cost };
}

export default function (pi: ExtensionAPI) {
	let triggerRefresh: (() => void) | undefined;

	pi.on("message_end", (event) => {
		if (event.message.role !== "assistant") return;
		triggerRefresh?.();
	});

	pi.on("session_start", (_event, ctx) => {
		ctx.ui.setFooter((tui, _theme, footerData) => {
			let cached = ctx.model?.id ?? "pi";
			let refreshing = false;
			let consecutiveFailures = 0;

			const refresh = () => {
				if (refreshing) return;
				refreshing = true;

				const usage = ctx.getContextUsage();
				const payload = JSON.stringify({
					cwd: ctx.cwd,
					branch: footerData.getGitBranch() || null,
					model: ctx.model ? { id: ctx.model.id, provider: ctx.model.provider } : null,
					context_window: usage?.percent != null ? { used_percentage: usage.percent } : null,
					tokens: sessionTokens(ctx),
				});

				const child = spawn("python3", [STATUSLINE_BIN], { stdio: ["pipe", "pipe", "pipe"] });
				let out = "";
				let err = "";
				child.stdout.on("data", (chunk: Buffer) => {
					out += chunk.toString();
				});
				child.stderr.on("data", (chunk: Buffer) => {
					err += chunk.toString();
				});
				const onFailure = (detail: string) => {
					// A one-shot notify, not a repeat-per-refresh spam: the interval
					// keeps retrying silently after that in case it's transient, but
					// the failure is surfaced at least once instead of leaving a
					// stale placeholder forever with no way to tell it's broken.
					consecutiveFailures += 1;
					if (consecutiveFailures === 1) {
						ctx.ui.notify(`omniline-statusline: ${detail}`, "warning");
					}
				};
				child.on("close", (code) => {
					refreshing = false;
					if (code === 0 && out.trim()) {
						cached = out.trim();
						consecutiveFailures = 0;
						tui.requestRender();
					} else {
						onFailure(`bin/pi-statusline exited ${code}${err.trim() ? `: ${err.trim()}` : ""}`);
					}
				});
				child.on("error", (spawnErr) => {
					refreshing = false;
					onFailure(`failed to spawn python3: ${spawnErr.message}`);
				});
				child.stdin.write(payload);
				child.stdin.end();
			};

			triggerRefresh = refresh;
			const unsubBranch = footerData.onBranchChange(refresh);
			refresh();
			const timer = setInterval(refresh, REFRESH_MS);

			return {
				dispose: () => {
					unsubBranch();
					clearInterval(timer);
					triggerRefresh = undefined;
				},
				invalidate() {},
				render(width: number): string[] {
					return [truncateToWidth(cached, width)];
				},
			};
		});
	});
}
