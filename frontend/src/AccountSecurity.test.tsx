// @vitest-environment jsdom
import {it,expect,vi,afterEach} from "vitest";
import {render,screen,fireEvent,cleanup,waitFor} from "@testing-library/react";
import {MemoryRouter} from "react-router-dom";
import {AccountSecurity,PasswordRecovery} from "./AccountSecurity";
import {StudioPreferences} from "./StudioPreferences";
import {api} from "./api";
vi.mock("./api",()=>({api:vi.fn(),json:JSON.stringify}));
afterEach(()=>{cleanup();vi.clearAllMocks();window.history.replaceState(null,"","/");});
it("checks password confirmation before making a change",async()=>{
  render(<MemoryRouter><AccountSecurity onDeleted={async()=>{}}/></MemoryRouter>);
  fireEvent.change(screen.getByLabelText("Current password"),{target:{value:"current-pass"}});
  fireEvent.change(screen.getByLabelText("New password"),{target:{value:"new-password"}});
  fireEvent.change(screen.getByLabelText("Confirm new password"),{target:{value:"different-password"}});
  fireEvent.submit(screen.getByText("Change password").closest("form")!);
  expect(api).not.toHaveBeenCalled();
  expect(screen.getAllByText("New passwords do not match.").length).toBeGreaterThan(0);
});
it("submits a recovery fragment and clears it on success",async()=>{
  window.history.replaceState(null,"","/reset-password#secret-token");
  vi.mocked(api).mockResolvedValue({ok:true});
  render(<MemoryRouter><PasswordRecovery reset/></MemoryRouter>);
  fireEvent.change(screen.getByLabelText("New password"),{target:{value:"new-password"}});
  fireEvent.change(screen.getByLabelText("Confirm password"),{target:{value:"new-password"}});
  fireEvent.submit(screen.getByText("Reset password").closest("form")!);
  await waitFor(()=>expect(api).toHaveBeenCalledWith("/auth/reset-password",expect.objectContaining({body:expect.stringContaining('"token":"secret-token"')})));
  await waitFor(()=>expect(window.location.hash).toBe(""));
});
it("saves preferences to the server before reporting success",async()=>{
  const store=new Map<string,string>();
  vi.stubGlobal("localStorage",{getItem:(k:string)=>store.get(k)??null,setItem:(k:string,v:string)=>store.set(k,v)});
  vi.mocked(api).mockResolvedValue({resolution:720});
  render(<StudioPreferences userId="remote" synced/>);
  fireEvent.change(screen.getByLabelText("Default export resolution"),{target:{value:"720"}});
  await waitFor(()=>expect(api).toHaveBeenCalledWith("/me/preferences",expect.objectContaining({method:"PUT"})));
  expect(await screen.findByText("Preferences saved to your account.")).toBeTruthy();
  vi.unstubAllGlobals();
});
it("shows required field errors and focuses the first invalid password",()=>{
  render(<MemoryRouter><AccountSecurity onDeleted={async()=>{}}/></MemoryRouter>);
  fireEvent.submit(screen.getByText("Change password").closest("form")!);
  expect(api).not.toHaveBeenCalled();
  const current=screen.getByLabelText("Current password");
  expect(current.getAttribute("aria-invalid")).toBe("true");
  expect(document.activeElement).toBe(current);
  expect(screen.getAllByText("This field is required.").length).toBe(3);
});
it("places a server password error beneath the current-password field",async()=>{
  vi.mocked(api).mockRejectedValue(new Error("Current password is incorrect"));
  render(<MemoryRouter><AccountSecurity onDeleted={async()=>{}}/></MemoryRouter>);
  fireEvent.change(screen.getByLabelText("Current password"),{target:{value:"wrong-password"}});
  fireEvent.change(screen.getByLabelText("New password"),{target:{value:"new-password"}});
  fireEvent.change(screen.getByLabelText("Confirm new password"),{target:{value:"new-password"}});
  fireEvent.submit(screen.getByText("Change password").closest("form")!);
  expect(await screen.findByText("Current password is incorrect")).toBeTruthy();
  expect(screen.getByLabelText("Current password").getAttribute("aria-describedby")).toBeTruthy();
});
