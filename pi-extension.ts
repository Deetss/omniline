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
import { fileURLToPath } from "node:url";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";
import { truncateToWidth } from "@earendil-works/pi-tui";

const STATUSLINE_BIN = fileURLToPath(new URL("./bin/pi-statusline", import.meta.url));
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

				const child = spawn("python3", [STATUSLINE_BIN], { stdio: ["pipe", "pipe", "ignore"] });
				let out = "";
				child.stdout.on("data", (chunk: Buffer) => {
					out += chunk.toString();
				});
				child.on("close", (code) => {
					refreshing = false;
					if (code === 0 && out.trim()) {
						cached = out.trim();
						tui.requestRender();
					}
				});
				child.on("error", () => {
					refreshing = false;
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
