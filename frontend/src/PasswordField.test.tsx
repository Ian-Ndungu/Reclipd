// @vitest-environment jsdom
import {it,expect,vi} from "vitest";
import {render,screen,fireEvent} from "@testing-library/react";
import {PasswordField} from "./PasswordField";
it("reveals only its own password and never submits the form",()=>{
  const submit=vi.fn();
  const view=render(<form onSubmit={submit}>
    <PasswordField label="New password" name="password" autoComplete="new-password"/>
    <PasswordField label="Confirm password" name="confirm"/>
  </form>);
  const input=screen.getByLabelText("New password") as HTMLInputElement;
  fireEvent.change(input,{target:{value:"typed-password"}});
  expect(input.type).toBe("password");
  fireEvent.click(screen.getByRole("button",{name:"Show new password"}));
  expect(input.type).toBe("text");
  expect(input.value).toBe("typed-password");
  expect((screen.getByLabelText("Confirm password") as HTMLInputElement).type).toBe("password");
  fireEvent.click(screen.getByRole("button",{name:"Hide new password"}));
  expect(input.type).toBe("password");
  expect(submit).not.toHaveBeenCalled();
  view.unmount();
});
