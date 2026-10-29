export type FieldErrors = Record<string,string>;
export function validateFields(form:HTMLFormElement):FieldErrors {
  const errors:FieldErrors={};
  for(const input of Array.from(form.querySelectorAll<HTMLInputElement>("input[name]"))) {
    if(input.disabled)continue;
    if(input.required&&!input.value.trim()) errors[input.name]="This field is required.";
    else if(input.type==="email"&&!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(input.value)) errors[input.name]="Enter a valid email address.";
    else if(input.minLength>0&&input.value.length<input.minLength) errors[input.name]=`Use at least ${input.minLength} characters.`;
    else if(input.maxLength>0&&input.value.length>input.maxLength) errors[input.name]=`Use no more than ${input.maxLength} characters.`;
    else if(input.name==="confirmation"&&input.value!=="DELETE") errors[input.name]="Type DELETE exactly to confirm.";
  }
  return errors;
}
export function focusError(form:HTMLFormElement,errors:FieldErrors){
  const name=Object.keys(errors)[0];
  const input=Array.from(form.querySelectorAll<HTMLInputElement>("input[name]")).find(i=>i.name===name);
  input?.focus();
}
