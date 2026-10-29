import {validateFields,focusError,type FieldErrors} from "./formErrors";
import {PasswordField} from "./PasswordField";
import {useState} from "react";
import {Link, useNavigate} from "react-router-dom";
import {api,json} from "./api";

export function AccountSecurity({onDeleted}:{onDeleted:()=>Promise<void>}) {
  const [busy,setBusy]=useState(false),[message,setMessage]=useState(""),[deleting,setDeleting]=useState(false);
  const [errors,setErrors]=useState<FieldErrors>({});
  const [deleteErrors,setDeleteErrors]=useState<FieldErrors>({});
  const [deleteMessage,setDeleteMessage]=useState("");
  const navigate=useNavigate();
  return <>
    <section className="panel settings-section account-security"><h2>Password & security</h2>
      <p className="muted">Changing your password signs out your other sessions.</p>
      <form noValidate onChange={e=>{if(!(e.target instanceof HTMLInputElement))return;const name=e.target.name;setErrors(old=>({...old,[name]:""}));setMessage("");}} onSubmit={async e=>{
        e.preventDefault();const form=e.currentTarget;const data=new FormData(form);
        const invalid=validateFields(form);
        if(data.get("new_password")!==data.get("confirm")) invalid.confirm="New passwords do not match.";
        if(data.get("new_password") && data.get("new_password")===data.get("current_password")) invalid.new_password="Choose a different new password.";
        setErrors(invalid);
        if(Object.keys(invalid).length){focusError(form,invalid);return;}
        setBusy(true);setMessage("");
        try{await api("/auth/change-password",{method:"POST",body:json(Object.fromEntries(data))});form.reset();setMessage("Password changed. Other sessions have been signed out.");}
        catch(e){const text=(e as Error).message;
          if(text==="Current password is incorrect"){setErrors({current_password:text});focusError(form,{current_password:text});}
          else setMessage(text);
        }finally{setBusy(false);}
      }}>
        <PasswordField error={errors.current_password} label="Current password" name="current_password"  autoComplete="current-password" required maxLength={128}/>
        <PasswordField error={errors.new_password} label="New password" name="new_password"  autoComplete="new-password" required minLength={10} maxLength={128}/>
        <PasswordField error={errors.confirm} label="Confirm new password" name="confirm"  autoComplete="new-password" required minLength={10} maxLength={128}/>
        <button className="button primary" disabled={busy}>Change password</button>
      </form>
      <Link className="text-link" to="/forgot-password">Forgot your password?</Link>
      <p role="status">{message}</p>
    </section>
    <section className="panel settings-section account-security"><h2>Delete account</h2>
      <p className="muted">Permanently removes your profile, projects, clips, assets and credits. Transaction records and an anonymous trial-abuse prevention record are retained. Legacy temporary previews expire within seven days.</p>
      {!deleting ? <button className="button secondary" onClick={()=>{setDeleting(true);setDeleteMessage("");setDeleteErrors({});}}>Delete my account</button> :
      <form noValidate onChange={e=>{if(!(e.target instanceof HTMLInputElement))return;const name=e.target.name;setDeleteErrors(old=>({...old,[name]:""}));setDeleteMessage("");}} onSubmit={async e=>{
        e.preventDefault();const form=e.currentTarget;const invalid=validateFields(form);
        setDeleteErrors(invalid);if(Object.keys(invalid).length){focusError(form,invalid);return;}
        setBusy(true);setDeleteMessage("");
        try {
          await api("/me",{method:"DELETE",body:json(Object.fromEntries(new FormData(e.currentTarget)))});
          await onDeleted();navigate("/auth",{replace:true});
        }catch(e){const text=(e as Error).message;
          if(text==="Password is incorrect"){setDeleteErrors({password:text});focusError(form,{password:text});}
          else setDeleteMessage(text);
        }finally{setBusy(false);}
      }}>
        <p>This cannot be undone. Cancel clipping and wait for active exports before continuing.</p>
        <PasswordField error={deleteErrors.password} label="Password" name="password"  autoComplete="current-password" required/>
        <label htmlFor="delete-confirmation">Type DELETE to confirm</label>
        <input id="delete-confirmation" name="confirmation" pattern="DELETE" autoComplete="off" required aria-invalid={!!deleteErrors.confirmation} aria-describedby={deleteErrors.confirmation?"delete-confirmation-error":undefined}/>
        {deleteErrors.confirmation&&<p id="delete-confirmation-error" className="field-error" role="alert">{deleteErrors.confirmation}</p>}
        <div className="actions"><button className="button secondary" type="button" disabled={busy} onClick={()=>setDeleting(false)}>Keep account</button>
        <button className="button primary" disabled={busy}>Permanently delete account</button></div>
      </form>}
      {deleting && <p role="alert">{deleteMessage}</p>}
    </section>
  </>;
}
export function PasswordRecovery({reset=false}:{reset?:boolean}) {
  const [token]=useState(()=>window.location.hash.slice(1));
  const [busy,setBusy]=useState(false),[message,setMessage]=useState(""),[done,setDone]=useState(false);
  const [errors,setErrors]=useState<FieldErrors>({});
  return <main className="auth-form recovery-form">
    <h1>{reset?"Choose a new password":"Reset your password"}</h1>
    <p>{reset?"Use at least 10 characters.":"Enter your account email to receive a reset link."}</p>
    {!done && <form noValidate onChange={e=>{if(!(e.target instanceof HTMLInputElement))return;const name=e.target.name;setErrors(old=>({...old,[name]:""}));setMessage("");}} onSubmit={async e=>{
      e.preventDefault();const form=e.currentTarget;const data=new FormData(form);
      const invalid=validateFields(form);
      if(reset && data.get("new_password")!==data.get("confirm")) invalid.confirm="Passwords do not match.";
      setErrors(invalid);if(Object.keys(invalid).length){focusError(form,invalid);return;}
      setBusy(true);setMessage("");
      try {
        const result=await api<{message?:string}>(reset?"/auth/reset-password":"/auth/forgot-password",
          {method:"POST",body:json({...Object.fromEntries(data),...(reset?{token}:{})})});
        setMessage(result.message || "Password reset. Sign in with your new password.");setDone(true);
        if(reset) window.history.replaceState(null,"",window.location.pathname);
      }catch(e){setMessage((e as Error).message);}finally{setBusy(false);}
    }}>
      {reset ? <>
        <PasswordField error={errors.new_password} label="New password" name="new_password"  autoComplete="new-password" minLength={10} maxLength={128} required/>
        <PasswordField error={errors.confirm} label="Confirm password" name="confirm"  autoComplete="new-password" minLength={10} maxLength={128} required/>
      </>:<div><label htmlFor="recovery-email">Email</label><input id="recovery-email" name="email" type="email" autoComplete="email" required aria-invalid={!!errors.email} aria-describedby={errors.email?"recovery-email-error":undefined}/>
      {errors.email&&<p id="recovery-email-error" className="field-error" role="alert">{errors.email}</p>}</div>}
      <button className="button primary" disabled={busy || (reset&&!token)}>{busy?"Please wait…":reset?"Reset password":"Send reset link"}</button>
    </form>}
    {reset&&!token&&<p role="alert">Open the full link from your reset email.</p>}
    <p role="status">{message}</p><Link to="/auth">Back to sign in</Link>
  </main>;
}
