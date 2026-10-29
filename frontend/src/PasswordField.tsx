import {useId,useState,type InputHTMLAttributes} from "react";
import {Eye,EyeOff} from "lucide-react";

export function PasswordField({label,error,...props}:Omit<InputHTMLAttributes<HTMLInputElement>,"type"|"id"> & {label:string;error?:string}) {
  const id=useId();
  const [visible,setVisible]=useState(false);
  return <div className="password-field">
    <label htmlFor={id}>{label}</label>
    <div className="password-input">
      <input {...props} id={id} aria-invalid={!!error} aria-describedby={error?id+"-error":undefined} type={visible?"text":"password"}/>
      <button type="button" className="password-toggle" disabled={props.disabled}
        aria-label={`${visible?"Hide":"Show"} ${label.toLowerCase()}`}
        aria-controls={id} aria-pressed={visible} onClick={()=>setVisible(v=>!v)}>
        {visible?<EyeOff size={20} aria-hidden="true"/>:<Eye size={20} aria-hidden="true"/>}
      </button>
    </div>
    {error && <p id={id+"-error"} className="field-error" role="alert">{error}</p>}
  </div>;
}
