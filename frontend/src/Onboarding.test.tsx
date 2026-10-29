// @vitest-environment jsdom
import {it,expect,vi,afterEach} from "vitest";
import {render,screen,fireEvent,waitFor,cleanup} from "@testing-library/react";
import {MemoryRouter} from "react-router-dom";
import {Onboarding} from "./Onboarding";
import {api} from "./api";
import {readDraft,saveDraft} from "./draft";
vi.mock("./api",()=>({api:vi.fn(),json:JSON.stringify}));
afterEach(()=>{cleanup();vi.clearAllMocks();sessionStorage.clear();});
it("persists completion and preserves the pasted source when choosing manual editing",async()=>{
  saveDraft({url:"https://example.org/video.mp4"});
  vi.mocked(api).mockResolvedValue({});
  const complete=vi.fn().mockResolvedValue(undefined);
  render(<MemoryRouter><Onboarding onComplete={complete}/></MemoryRouter>);
  fireEvent.click(screen.getByRole("radio",{name:/Edit a video yourself/}));
  fireEvent.click(screen.getByText("Continue"));
  fireEvent.click(screen.getByText("Create my first project"));
  await waitFor(()=>expect(complete).toHaveBeenCalledOnce());
  expect(api).toHaveBeenCalledWith("/me/preferences",{method:"PUT",body:JSON.stringify({onboarding_completed:true})});
  expect(readDraft()).toMatchObject({workflow:"manual",mode:"upload",url:"https://example.org/video.mp4"});
});
it("keeps the guide open with a retryable error when saving fails",async()=>{
  vi.mocked(api).mockRejectedValue(new Error("Connection lost"));
  const complete=vi.fn();
  render(<MemoryRouter><Onboarding onComplete={complete}/></MemoryRouter>);
  fireEvent.click(screen.getByText("Skip introduction"));
  expect((await screen.findByRole("alert")).textContent).toContain("Connection lost");
  expect(complete).not.toHaveBeenCalled();
});
