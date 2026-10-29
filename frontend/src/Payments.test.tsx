// @vitest-environment jsdom
import {it,expect,vi,afterEach} from "vitest";
import {render,screen,waitFor,cleanup} from "@testing-library/react";
import {Payments} from "./Payments";
import {api} from "./api";
vi.mock("./api",()=>({api:vi.fn(),json:JSON.stringify}));
const billing={enabled:false,paypal_enabled:false,mode:"test",packs:[{id:"starter",name:"Starter",amount_usd:10,minutes:100}],payments:[]};
afterEach(()=>{cleanup();vi.clearAllMocks();window.history.replaceState(null,"","/");});
it("keeps checkout unavailable without sandbox configuration",async()=>{
  vi.mocked(api).mockResolvedValue(billing);
  render(<Payments unlimited={false} onVerified={()=>{}}/>);
  expect((await screen.findByText("Checkout unavailable") as HTMLButtonElement).disabled).toBe(true);
});
it("verifies PayPal returns through the PayPal endpoint",async()=>{
  window.history.replaceState(null,"","/studio/billing?paypal_reference=owned-reference&token=ORDER123");
  vi.mocked(api).mockImplementation(async(path)=>path==="/billing"?billing:{status:"success"});
  const updated=vi.fn();
  render(<Payments unlimited={false} onVerified={updated}/>);
  await waitFor(()=>expect(api).toHaveBeenCalledWith("/billing/paypal/verify/owned-reference",{method:"POST"}));
  await waitFor(()=>expect(updated).toHaveBeenCalledOnce());
  expect(window.location.search).toBe("");
});
it("cancellation does not capture a payment",async()=>{
  window.history.replaceState(null,"","/studio/billing?paypal_cancelled=1");
  vi.mocked(api).mockResolvedValue(billing);
  render(<Payments unlimited={false} onVerified={()=>{}}/>);
  expect(await screen.findByText("PayPal checkout cancelled. No credits have been added.")).toBeTruthy();
  expect(vi.mocked(api).mock.calls.every(([path])=>path==="/billing")).toBe(true);
});
