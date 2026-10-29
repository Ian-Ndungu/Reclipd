// @vitest-environment jsdom
import { it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App from "./App";
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
it("shows the honest empty workspace and navigates to real media input", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => ({
      ok: true,
      json: async () =>
        url.endsWith("/me")
          ? {
              id: "u",
              name: "Taylor",
              email: "t@example.com",
              used_seconds: 0,
              is_admin: false,
            }
          : [],
    })),
  );
  render(
    <MemoryRouter initialEntries={["/studio"]}>
      <App />
    </MemoryRouter>,
  );
  expect(await screen.findByText("Let’s make something, Taylor.")).toBeTruthy();
  expect(await screen.findByText("Your next story starts here")).toBeTruthy();
  fireEvent.click(screen.getByRole("link", { name: "Create a project" }));
  expect(await screen.findByText("How would you like to create?")).toBeTruthy();
  expect(
    screen.getByPlaceholderText("Paste YouTube video URL here..."),
  ).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: /Manual Editor.*Choose every cut/ }));
  expect(screen.getByLabelText("Choose video")).toBeTruthy();
  expect(screen.getByRole("button", {name: "Open Manual Editor"})).toBeTruthy();
  expect(screen.queryByRole("spinbutton", {name: "Minimum seconds"})).toBeNull();
  fireEvent.click(screen.getByRole("button", {name: /AI Clips.*Find highlights/}));
  expect(screen.getByRole("spinbutton", {name: "Minimum seconds"})).toBeTruthy();
});
it("shows API authentication failures to the user", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: false,
      status: 401,
      json: async () => ({ detail: "Email or password is incorrect" }),
    })),
  );
  render(
    <MemoryRouter initialEntries={["/auth"]}>
      <App />
    </MemoryRouter>,
  );
  fireEvent.change(await screen.findByLabelText("Email address"), {
    target: { value: "a@example.com" },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "bad-password" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Enter studio" }));
  expect(await screen.findByRole("alert")).toHaveProperty(
    "textContent",
    "Email or password is incorrect",
  );
});
it("preserves a guest's link through login without starting a paid or processing job", async () => {
  window.sessionStorage.clear();
  let signed = false;
  const requests: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      requests.push(url);
      if (url.endsWith("/auth/login")) {
        signed = true;
        return { ok: true, json: async () => ({}) };
      }
      if (url.endsWith("/me"))
        return signed
          ? {
              ok: true,
              json: async () => ({
                id: "u",
                name: "Guest creator",
                email: "g@example.com",
                used_seconds: 0,
              }),
            }
          : {
              ok: false,
              status: 401,
              json: async () => ({ detail: "Please sign in" }),
            };
      return { ok: true, json: async () => [] };
    }),
  );
  render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>,
  );
  fireEvent.change(await screen.findByLabelText("Video link"), {
    target: { value: "https://youtu.be/abcdefghijk" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Generate AI Clips" }));
  expect(await screen.findByText("Let’s give your clips a home.")).toBeTruthy();
  expect(screen.queryByLabelText("Email address")).toBeNull();
  expect(screen.getByRole("link", {name: "Create an account"}).getAttribute("href")).toBe("/auth?mode=register");
  fireEvent.click(screen.getByRole("link", {name: "Sign in to continue"}));
  expect(await screen.findByText("Welcome back.")).toBeTruthy();
  expect(
    screen.getByRole("button", { name: "Create an account" }),
  ).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Email address"), {
    target: { value: "g@example.com" },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "safe-test-password" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Enter studio" }));
  expect(
    await screen.findByPlaceholderText("Paste YouTube video URL here..."),
  ).toHaveProperty("value", "https://youtu.be/abcdefghijk");
  expect(requests).not.toContain("/api/projects/import");
  window.sessionStorage.clear();
});

it("lets creators set headline length, edit a draft and apply the edited overlay", async () => {
  const clip = {id:'c', title:'Camera in rain', revision:0, headlines:[], edits:{segments:[{start:0,end:10}], words:[{start:0,end:1,word:'Camera'}]}};
  let generated: any;
  let applied: any;
  vi.stubGlobal('fetch', vi.fn(async (url: string, options?: RequestInit) => {
    let result: any = [];
    if (url.endsWith('/me')) result = {id:'u', name:'Taylor', used_seconds:0};
    else if (url.endsWith('/projects')) result = [{id:'p',name:'Rain test',status:'ready'}];
    else if (url.endsWith('/projects/p')) result = {clips:[clip]};
    else if (url.endsWith('/headlines')) {
      generated = JSON.parse(options!.body as string);
      result = [{text:'Camera in the rain',tone:'concise',source:'deterministic transcript template'}];
    } else if (url.endsWith('/clips/c')) {
      applied = JSON.parse(options!.body as string);
      result = {...clip, revision:1, edits:applied.edits, headlines:[{text:'Camera in the rain',tone:'concise',source:'deterministic transcript template'}]};
    }
    return {ok:true,json:async()=>result};
  }));
  render(<MemoryRouter initialEntries={['/studio/headlines']}><App /></MemoryRouter>);
  await screen.findByText('Rain test');
  fireEvent.change(screen.getByLabelText('Project'), {target:{value:'p'}});
  await screen.findByText('Camera in rain');
  fireEvent.change(screen.getByLabelText('Headline length'), {target:{value:'60'}});
  fireEvent.click(screen.getByRole('button',{name:'Generate headlines'}));
  const draft = await screen.findByLabelText('Headline 1');
  expect(generated.max_characters).toBe(60);
  fireEvent.change(draft,{target:{value:'Testing a camera in rain'}});
  fireEvent.click(screen.getByRole('button',{name:'Use as overlay'}));
  await screen.findByText('Headline 1 applied to the video overlay.');
  expect(applied.edits.headline).toBe('Testing a camera in rain');
  expect(applied.edits.show_headline).toBe(true);
});
it("deletes a project only after confirmation", async () => {
  const request = vi.fn(async (url: string, options?: RequestInit) => ({
    ok: true,
    json: async () => url.endsWith('/me')
      ? {id:'u',name:'Taylor',email:'t@example.com',used_seconds:0,is_admin:false}
      : options?.method === 'DELETE' ? {deleted:true}
      : url.endsWith('/projects/p') ? {id:'p',name:'Interview',status:'ready',media:{duration:30},analysis:{},clips:[]}
      : [],
  }));
  vi.stubGlobal('fetch', request);
  HTMLDialogElement.prototype.showModal = function() {this.setAttribute('open', '');};
  HTMLDialogElement.prototype.close = function() {this.removeAttribute('open');};
  render(<MemoryRouter initialEntries={['/studio/projects/p']}><App /></MemoryRouter>);
  const button = await screen.findByRole('button', {name:'Delete project'});
  fireEvent.click(button);
  expect(request.mock.calls.some(([, o]) => o?.method === 'DELETE')).toBe(false);
  fireEvent.click(await screen.findByRole('button', {name:'Keep project'}));
  fireEvent.click(button);
  fireEvent.click(await screen.findByRole('button', {name:'Yes, delete project'}));
  expect(await screen.findByText('Your next story starts here')).toBeTruthy();
  expect(await screen.findByText('Project deleted')).toBeTruthy();
  expect(request.mock.calls.some(([url, o]) => url === '/api/projects/p' && o?.method === 'DELETE')).toBe(true);
});
it('clears a transient progress error after reconnecting', async () => {
  let polls = 0;
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    if (url.endsWith('/me')) return {ok:true,json:async()=>({id:'u',name:'Taylor'})};
    if (url.endsWith('/projects/p') && ++polls === 1) return {ok:false,status:502,json:async()=>{throw Error('HTML');}};
    return {ok:true,json:async()=>({id:'p',name:'Recovered project',status:'ready',media:{},analysis:{},clips:[]})};
  }));
  render(<MemoryRouter initialEntries={['/studio/projects/p']}><App/></MemoryRouter>);
  expect(await screen.findByText(/Reconnecting automatically/)).toBeTruthy();
  expect(await screen.findByText('Recovered project', {}, {timeout:4000})).toBeTruthy();
  expect(screen.queryByText(/Reconnecting automatically/)).toBeNull();
});
it('shows the real unlimited billing allowance without a payment action', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => ({ok:true,json:async()=>url.endsWith('/me') ? {id:'u',name:'Taylor'} : {plan:'Unlimited',used_seconds:600,limit_seconds:null,billing_enabled:false}})));
  render(<MemoryRouter initialEntries={['/studio/billing']}><App/></MemoryRouter>);
  expect(await screen.findByText('Unlimited workspace')).toBeTruthy();
  expect(screen.getByText('No active subscription')).toBeTruthy();
  expect(screen.getByText(/10 minutes used/)).toBeTruthy();
});
it('offers cancellation instead of deletion during processing', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url: string, options?: RequestInit) => ({ok:true,json:async()=>url.endsWith('/me') ? {id:'u',name:'Taylor'} : {id:'p',name:'Active clip',status:options?.method === 'POST' ? 'cancelling' : 'processing',progress:40,stage:'Transcribing',media:{},analysis:{},clips:[]}})));
  render(<MemoryRouter initialEntries={['/studio/projects/p']}><App/></MemoryRouter>);
  fireEvent.click(await screen.findByRole('button',{name:'Cancel clipping'}));
  expect(await screen.findByText('Cancelling…')).toBeTruthy();
  expect(screen.queryByRole('button',{name:'Delete project'})).toBeNull();
});

it("offers a signed-in homepage handoff instead of redirecting through login", async () => {
  vi.stubGlobal("fetch", vi.fn(async (url: string) => ({
    ok: true,
    json: async () => url.endsWith("/me")
      ? {id: "u", name: "Taylor", email: "t@example.com", used_seconds: 0, is_admin: false}
      : [],
  })));
  render(<MemoryRouter initialEntries={["/"]}><App /></MemoryRouter>);
  const account = await screen.findByText("Your studio");
  expect(screen.queryByRole("link", {name: "Login"})).toBeNull();
  expect(screen.queryByText("Does RECLIPD use OpusClip?")).toBeNull();
  fireEvent.click(account);
  expect(screen.getByText("Welcome back")).toBeTruthy();
  fireEvent.click(screen.getByRole("link", {name: /Continue to studio/}));
  expect(await screen.findByText("Let’s make something, Taylor.")).toBeTruthy();
});

it("opens registration directly from the homepage account invitation", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => ({ok:false,status:401,json:async()=>({detail:"Please sign in"})})));
  render(<MemoryRouter initialEntries={["/auth?mode=register"]}><App /></MemoryRouter>);
  expect(await screen.findByRole("heading", {name:"Create your account"})).toBeTruthy();
  expect(screen.getByLabelText("Your name")).toBeTruthy();
});
