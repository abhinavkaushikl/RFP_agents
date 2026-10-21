import { useMutation } from "@tanstack/react-query";
import { Check, Copy, Download, ShieldCheck, ShieldOff } from "lucide-react";
import { motion } from "motion/react";
import { useState, type FormEvent } from "react";

import { useToast } from "@/components/Toast";
import { Button, Field, Notice, Panel, PanelHeader, StatusTag, TextInput } from "@/components/ui";
import { useAuth } from "@/hooks/useAuth";
import { api, ApiError, type MfaSetup } from "@/lib/api";
import { spring } from "@/lib/motion";

type Stage = "idle" | "setup" | "codes" | "disable";

const groups = (secret: string) => secret.replace(/(.{4})/g, "$1 ").trim();
const message = (err: unknown) => (err instanceof ApiError ? err.message : "Something went wrong. Try again.");

/** Turn authenticator-app sign-in on or off. Works with Google Authenticator, Microsoft Authenticator, Authy and 1Password. */
export function TwoStepPanel() {
  const { user, refreshUser } = useAuth();
  const toast = useToast();
  const enabled = Boolean(user?.mfa_enabled);
  const [stage, setStage] = useState<Stage>("idle");
  const [setup, setSetup] = useState<MfaSetup | null>(null);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [backupCodes, setBackupCodes] = useState<string[]>([]);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setStage("idle");
    setSetup(null);
    setCode("");
    setPassword("");
    setBackupCodes([]);
    setSaved(false);
    setError(null);
  };

  const start = useMutation({
    mutationFn: api.mfaSetup,
    onSuccess: (data) => {
      setSetup(data);
      setStage("setup");
      setError(null);
    },
    onError: (err) => setError(message(err)),
  });
  const enable = useMutation({
    mutationFn: () => api.mfaEnable(code.trim()),
    onSuccess: (data) => {
      setBackupCodes(data.backup_codes);
      setStage("codes");
      setCode("");
      setError(null);
    },
    onError: (err) => setError(message(err)),
  });
  const disable = useMutation({
    mutationFn: () => api.mfaDisable(password, code.trim()),
    onSuccess: async () => {
      await refreshUser();
      toast({ tone: "good", title: "Two-step sign-in is off" });
      reset();
    },
    onError: (err) => setError(message(err)),
  });

  const finish = async () => {
    await refreshUser();
    toast({ tone: "good", title: "Two-step sign-in is on", detail: "You'll be asked for a code each time you sign in." });
    reset();
  };

  const copy = async (text: string, what: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast({ tone: "good", title: `${what} copied` });
    } catch {
      toast({ tone: "bad", title: "Could not copy", detail: "Select it and copy it by hand." });
    }
  };
  const download = () => {
    const file = new Blob([`Proposal Builder backup codes for ${user?.email}\nEach works once. Keep them somewhere safe.\n\n${backupCodes.join("\n")}\n`], { type: "text/plain" });
    const url = URL.createObjectURL(file);
    const a = document.createElement("a");
    a.href = url;
    a.download = "proposal-builder-backup-codes.txt";
    a.click();
    URL.revokeObjectURL(url);
  };

  const submit = (action: () => void) => (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    action();
  };

  return (
    <Panel>
      <PanelHeader
        title="Two-step sign-in"
        description="Ask for a 6-digit code from an authenticator app each time you sign in, on top of your password."
        action={enabled ? <StatusTag tone="good">On</StatusTag> : <StatusTag tone="neutral">Off</StatusTag>}
      />
      <div className="flex flex-col gap-4 p-5">
        {stage === "idle" && (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="max-w-xl text-small text-ink-2">
              {enabled
                ? "Your account asks for a code from your authenticator app whenever you sign in. You also have backup codes in case you lose your phone."
                : "Works with Google Authenticator, Microsoft Authenticator, Authy and 1Password. It takes about a minute to set up."}
            </p>
            {enabled ? (
              <Button icon={<ShieldOff className="size-4" />} onClick={() => { setStage("disable"); setError(null); }}>Turn off</Button>
            ) : (
              <Button variant="primary" icon={<ShieldCheck className="size-4" />} loading={start.isPending} onClick={() => start.mutate()}>Turn on</Button>
            )}
          </div>
        )}

        {stage === "setup" && setup && (
          <motion.form initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={spring.smooth} onSubmit={submit(() => enable.mutate())} className="grid gap-6 sm:grid-cols-[auto_1fr]">
            <div className="flex flex-col items-center gap-2">
              {/* White card behind the code: authenticator apps need dark-on-light to scan reliably. */}
              <img src={setup.qr} alt="QR code to scan with your authenticator app" width={176} height={176} className="rounded-[12px] bg-white p-2" />
              <span className="text-caption text-ink-3">Scan with your app</span>
            </div>
            <div className="flex flex-col gap-4">
              <ol className="list-decimal space-y-1.5 pl-5 text-small text-ink-2">
                <li>Open your authenticator app and add an account by scanning the code.</li>
                <li>Can't scan? Enter this key by hand: <button type="button" onClick={() => copy(setup.secret, "Key")} className="ml-1 inline-flex items-center gap-1 rounded-[6px] bg-fill px-2 py-0.5 font-mono text-caption text-ink hover:bg-wash" title="Copy"><span>{groups(setup.secret)}</span><Copy className="size-3" aria-hidden /></button></li>
                <li>Type the 6-digit code the app shows to finish.</li>
              </ol>
              <Field label="Code from your app" htmlFor="mfa-code">
                <TextInput id="mfa-code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} autoFocus value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} placeholder="000000" className="max-w-40 font-mono tracking-[0.3em]" />
              </Field>
              {error && <Notice tone="bad" title="That didn't work">{error}</Notice>}
              <div className="flex gap-2">
                <Button variant="primary" type="submit" loading={enable.isPending} disabled={code.length !== 6}>Confirm and turn on</Button>
                <Button variant="ghost" type="button" onClick={reset}>Cancel</Button>
              </div>
            </div>
          </motion.form>
        )}

        {stage === "codes" && (
          <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={spring.smooth} className="flex flex-col gap-4">
            <Notice tone="warn" title="Save your backup codes now">
              Each code works once, in place of the app code, if you lose your phone. They won't be shown again.
            </Notice>
            <ul className="grid max-w-md grid-cols-2 gap-2 font-mono text-small text-ink" aria-label="Backup codes">
              {backupCodes.map((c) => <li key={c} className="rounded-[8px] border border-line bg-fill px-3 py-1.5 text-center tracking-wider">{c}</li>)}
            </ul>
            <div className="flex flex-wrap items-center gap-2">
              <Button icon={<Copy className="size-4" />} onClick={() => copy(backupCodes.join("\n"), "Backup codes")}>Copy all</Button>
              <Button icon={<Download className="size-4" />} onClick={download}>Download</Button>
            </div>
            <label className="flex items-center gap-2 text-small text-ink-2">
              <input type="checkbox" checked={saved} onChange={(e) => setSaved(e.target.checked)} className="size-4 accent-[var(--color-ion)]" />
              I've saved these somewhere safe
            </label>
            <div><Button variant="primary" icon={<Check className="size-4" />} disabled={!saved} onClick={finish}>Done</Button></div>
          </motion.div>
        )}

        {stage === "disable" && (
          <motion.form initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={spring.smooth} onSubmit={submit(() => disable.mutate())} className="flex max-w-md flex-col gap-4">
            <p className="text-small text-ink-2">To turn it off, confirm with your password and a current code (or a backup code).</p>
            <Field label="Password" htmlFor="off-pw">
              <TextInput id="off-pw" type="password" autoComplete="current-password" autoFocus value={password} onChange={(e) => setPassword(e.target.value)} />
            </Field>
            <Field label="Code from your app, or a backup code" htmlFor="off-code">
              <TextInput id="off-code" autoComplete="one-time-code" value={code} onChange={(e) => setCode(e.target.value)} className="font-mono" />
            </Field>
            {error && <Notice tone="bad" title="Could not turn it off">{error}</Notice>}
            <div className="flex gap-2">
              <Button variant="primary" type="submit" loading={disable.isPending} disabled={!password || !code.trim()}>Turn off</Button>
              <Button variant="ghost" type="button" onClick={reset}>Cancel</Button>
            </div>
          </motion.form>
        )}
      </div>
    </Panel>
  );
}
