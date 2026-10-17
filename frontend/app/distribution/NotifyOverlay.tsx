"use client";

import { useRef, useState } from "react";

const contacts = [
  {
    id: "dispatcher",
    label: "Supplier dispatch",
    name: "Dispatch team",
    role: "Supplier logistics",
    contactStatus: "Demo mode: nothing is sent",
  },
  {
    id: "kitchen",
    label: "Receiving kitchen",
    name: "Receiving team",
    role: "Kitchen operations",
    contactStatus: "Demo mode: nothing is sent",
  },
] as const;

export type NotifyTarget = { shipmentId: string; batchId: string; reason: string; supplier: string; recipient: string };

export default function NotifyOverlay({ target }: { target: NotifyTarget }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [selectedId, setSelectedId] = useState<(typeof contacts)[number]["id"]>("dispatcher");
  const [message, setMessage] = useState(`Please review shipment ${target.shipmentId} from batch ${target.batchId}. ${target.reason} Please keep this stock aside while the hold decision is made.`);
  const [notice, setNotice] = useState<"idle" | "previewed">("idle");
  const [callPreview, setCallPreview] = useState(false);
  const selected = contacts.find((contact) => contact.id === selectedId) ?? contacts[0];
  const organization = selected.id === "dispatcher" ? target.supplier : target.recipient;

  const close = () => {
    dialogRef.current?.close();
    setCallPreview(false);
  };

  return (
    <>
      <button type="button" onClick={() => dialogRef.current?.showModal()} className="group w-full rounded-[26px] border border-slate-200 bg-white p-2 text-slate-900 shadow-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600">
        <span className="flex min-h-48 flex-col items-center justify-center rounded-[20px] border border-slate-200 bg-slate-50/50 px-4 py-5 text-center transition-colors group-hover:border-amber-300 group-hover:bg-amber-50">
          <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">Contacts</span>
          <span className="relative mt-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-100 text-amber-700" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="currentColor" className="h-7 w-7"><path d="M12 2a2 2 0 0 0-2 1.7A5.5 5.5 0 0 0 6.5 9v2.5c0 1.8-.6 3.5-1.8 4.8l-.6.7a1 1 0 0 0 .7 1.7h14.4a1 1 0 0 0 .7-1.7l-.6-.7c-1.2-1.3-1.8-3-1.8-4.8V9A5.5 5.5 0 0 0 14 3.7 2 2 0 0 0 12 2Zm-2 18a2 2 0 0 0 4 0h-4Z" /></svg>
            <span className="absolute -right-1 -top-1 h-3.5 w-3.5 rounded-full border-2 border-white bg-rose-600" />
          </span>
          <strong className="mt-3 text-2xl font-bold tracking-tight">Early warning</strong>
          <span className="mt-2 text-xs font-medium text-slate-600">Heads-up before the hold decision</span>
        </span>
      </button>

      <dialog ref={dialogRef} onCancel={() => setCallPreview(false)} onClick={(event) => { if (event.target === dialogRef.current) close(); }} aria-labelledby="notify-title" className="notify-dialog m-auto w-[min(94vw,1020px)] max-h-[calc(100dvh-32px)] overflow-y-auto rounded-[28px] border border-rose-200 bg-[#fff8fa] p-0 text-[#0d293b] shadow-2xl backdrop:bg-slate-950/55 backdrop:backdrop-blur-sm">
        <div className="p-5 sm:p-6 lg:p-5">
          <div className="flex items-start justify-between gap-5 border-b border-rose-200 pb-4 lg:pb-3">
            <div>
              <h2 id="notify-title" className="text-2xl font-semibold tracking-tight">Send an early warning</h2>
            </div>
            <button type="button" onClick={close} aria-label="Close notification overlay" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-rose-200 bg-white text-xl text-slate-700 hover:bg-rose-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600">×</button>
          </div>

          <div className="mt-5 grid gap-4 lg:mt-4 lg:grid-cols-[minmax(0,1.3fr)_minmax(290px,0.8fr)]">
            <section aria-labelledby="contact-heading" className="rounded-2xl border border-rose-100 bg-white p-5 shadow-sm lg:p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.14em] text-rose-700">Contact details</p>
                  <h3 id="contact-heading" className="mt-1 text-lg font-semibold">Select recipient</h3>
                </div>
                <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold text-amber-800">Draft</span>
              </div>

              <fieldset className="mt-4 grid gap-3 sm:grid-cols-2 lg:mt-3 lg:gap-2">
                <legend className="sr-only">Choose a contact</legend>
                {contacts.map((contact) => (
                  <label key={contact.id} className={`cursor-pointer rounded-xl border p-4 transition-colors focus-within:ring-2 focus-within:ring-rose-500 focus-within:ring-offset-2 lg:p-3 ${selectedId === contact.id ? "border-rose-500 bg-rose-50" : "border-slate-200 hover:border-rose-300"}`}>
                    <input type="radio" name="notification-contact" value={contact.id} checked={selectedId === contact.id} onChange={() => { setSelectedId(contact.id); setNotice("idle"); setCallPreview(false); }} className="sr-only" />
                    <span className="flex items-start justify-between gap-2">
                      <span className="text-xs font-bold uppercase tracking-wide text-rose-700">{contact.label}</span>
                      <span aria-hidden="true" className={`h-4 w-4 shrink-0 rounded-full border-2 ${selectedId === contact.id ? "border-rose-600 bg-rose-600 shadow-[inset_0_0_0_3px_white]" : "border-slate-400"}`} />
                    </span>
                    <strong className="mt-2 block text-sm">{contact.name}</strong>
                    <span className="mt-1 block text-xs leading-5 text-slate-600">{contact.role}</span>
                  </label>
                ))}
              </fieldset>

              <div className="mt-4 grid gap-3 rounded-xl bg-slate-50 p-4 text-sm sm:grid-cols-2 lg:mt-3 lg:grid-cols-[1fr_1.3fr] lg:p-3">
                <div><p className="text-xs font-bold uppercase tracking-wide text-slate-500">Organization</p><p className="mt-1 font-medium">{organization}</p></div>
                <div><p className="text-xs font-bold uppercase tracking-wide text-slate-500">Contact status</p><p className="mt-1 break-words text-xs font-medium">{selected.contactStatus}</p></div>
              </div>

              <label htmlFor="notification-message" className="mt-4 block text-xs font-bold uppercase tracking-wide text-slate-600 lg:mt-3">Escalation draft</label>
              <textarea id="notification-message" rows={4} value={message} onChange={(event) => { setMessage(event.target.value); setNotice("idle"); }} className="mt-2 w-full resize-y rounded-xl border border-slate-200 bg-white p-3 text-sm leading-6 text-slate-800 outline-none focus:border-rose-500 focus:ring-2 focus:ring-rose-100 lg:mt-1 lg:min-h-[90px] lg:resize-none lg:p-2.5 lg:leading-5" />
              {/* Results show on the buttons themselves: a status line below would grow the centred dialog and shift every button. */}
              <button type="button" onClick={() => setNotice("previewed")} disabled={!message.trim()} className={`mt-3 w-full rounded-xl px-5 py-3 text-sm font-semibold text-white transition-colors active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600 lg:py-2.5 ${notice === "previewed" ? "bg-emerald-700 hover:bg-emerald-800" : "bg-slate-900 hover:bg-slate-700"}`}>{notice === "previewed" ? `✓ Draft ready for ${selected.name}` : `Preview notification for ${selected.label.toLowerCase()}`}</button>
              <p role="status" className="sr-only">{notice === "previewed" ? `Draft ready for ${selected.name}.` : ""}</p>
            </section>

            <section aria-labelledby="urgent-call-heading" className="flex flex-col justify-between rounded-2xl bg-gradient-to-br from-rose-600 via-rose-700 to-red-800 p-6 text-white shadow-xl lg:p-5">
              <div>
                <p className="inline-flex rounded-full bg-white/15 px-3 py-1 text-xs font-bold uppercase tracking-[0.14em] text-rose-50">Urgent call</p>
                <div aria-hidden="true" className="mt-6 flex h-14 w-14 items-center justify-center rounded-2xl border border-white/25 bg-white/15 text-3xl lg:mt-4 lg:h-12 lg:w-12">☎</div>
                <h3 id="urgent-call-heading" className="mt-4 text-2xl font-semibold tracking-tight">Call {selected.label.toLowerCase()}</h3>
                <p className="mt-2 text-sm leading-6 text-rose-50 lg:leading-5">{target.shipmentId} · {target.batchId}. Verify the recipient and product status before making contact.</p>
                <div className="mt-4 rounded-xl border border-white/20 bg-black/10 p-4 lg:p-3">
                  <p className="text-xs font-bold uppercase tracking-wide text-rose-100">Selected contact</p>
                  <p className="mt-2 font-semibold">{selected.name}</p>
                  <p className="mt-1 text-sm text-rose-100">{selected.role}</p>
                </div>
              </div>
              <div className="mt-4">
                <button type="button" onClick={() => setCallPreview(true)} className="w-full rounded-xl bg-white px-5 py-3.5 text-sm font-bold text-rose-800 shadow-sm transition-colors hover:bg-rose-50 active:scale-[0.98] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white lg:py-3">{callPreview ? `✓ Call brief ready for ${selected.name}` : "Prepare call brief"}</button>
                <p role="status" className="sr-only">{callPreview ? `Call brief ready for ${selected.name}.` : ""}</p>
                <p className="mt-2 text-center text-xs text-rose-100">Demo mode: no call is placed.</p>
              </div>
            </section>
          </div>
        </div>
      </dialog>
    </>
  );
}
