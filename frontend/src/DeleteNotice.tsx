import {createContext, useContext, useEffect, useRef, useState, type ReactNode} from 'react';
import {Check, Trash2, X} from 'lucide-react';
const Notices = createContext({confirmDelete: async (_name: string) => false, notify: (_message: string) => {}});
export const useDeleteNotice = () => useContext(Notices);
export function DeleteNoticeProvider({children}: {children: ReactNode}) {
  const [name, setName] = useState<string | null>(null);
  const [toast, setToast] = useState('');
  const dialog = useRef<HTMLDialogElement>(null);
  const resolve = useRef<((value: boolean) => void) | null>(null);
  const finish = (value: boolean) => {
    dialog.current?.close();
    setName(null);
    resolve.current?.(value);
    resolve.current = null;
  };
  useEffect(() => { if (name !== null) dialog.current?.showModal(); }, [name]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(''), 7000);
    return () => clearTimeout(timer);
  }, [toast]);
  return <Notices.Provider value={{confirmDelete: (projectName) => new Promise<boolean>(done => {
    resolve.current = done; setName(projectName);
  }), notify: setToast}}>
    {children}
    <dialog ref={dialog} className="delete-dialog" aria-labelledby="delete-title" aria-describedby="delete-description"
      onCancel={event => {event.preventDefault(); finish(false);}}>
      <div className="delete-icon"><Trash2 size={24}/></div>
      <h2 id="delete-title">Delete this project?</h2>
      <p id="delete-description"><strong>{name}</strong> and its clips and exports will be permanently removed. This cannot be undone.</p>
      <div className="delete-actions">
        <button className="button secondary" autoFocus onClick={() => finish(false)}>Keep project</button>
        <button className="button delete-confirm" onClick={() => finish(true)}>Yes, delete project</button>
      </div>
    </dialog>
    <div className="delete-toast-region" role="status" aria-live="polite" aria-atomic="true">
      {toast && <div className="delete-toast"><Check size={22}/><div><strong>Project deleted</strong><p>{toast}</p></div><button aria-label="Dismiss notification" onClick={() => setToast('')}><X size={18}/></button></div>}
    </div>
  </Notices.Provider>;
}
