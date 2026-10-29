// @vitest-environment jsdom
import {it, expect, vi, beforeEach, afterEach} from "vitest";
import {render,screen,fireEvent,cleanup} from "@testing-library/react";
import {ExportDialog} from "./ExportDialog";
import {type Edits,defaultCaption} from "./types";
beforeEach(()=>{
  HTMLDialogElement.prototype.showModal=function(){this.setAttribute("open","");};
  HTMLDialogElement.prototype.close=function(){this.removeAttribute("open");};
});
afterEach(cleanup);
const edits={segments:[{start:0,end:20}],captions:defaultCaption,resolution:1080,speed:2,watermark:true} as Edits;
it("requires confirmation and lets paid users toggle the watermark",()=>{
  const confirm=vi.fn(), watermark=vi.fn();
  render(<ExportDialog open title="My clip" edits={edits} quote={{seconds:10,reused:false}}
    busy={false} error="" canRemoveWatermark onWatermark={watermark} onClose={()=>{}} onConfirm={confirm}/>);
  expect(confirm).not.toHaveBeenCalled();
  expect(screen.getByText("10.0 seconds")).toBeTruthy();
  fireEvent.click(screen.getByRole("checkbox"));
  expect(watermark).toHaveBeenCalledWith(false);
  fireEvent.click(screen.getByText("Confirm export"));
  expect(confirm).toHaveBeenCalledOnce();
});
it("locks free watermark and prevents confirming before the quote arrives",()=>{
  render(<ExportDialog open title="My clip" edits={{...edits,watermark:false}} quote={null}
    busy={false} error="" canRemoveWatermark={false} onWatermark={()=>{}} onClose={()=>{}} onConfirm={()=>{}}/>);
  const checkbox=screen.getByRole("checkbox") as HTMLInputElement;
  expect(checkbox.checked).toBe(true);
  expect(checkbox.disabled).toBe(true);
  expect((screen.getByText("Confirm export") as HTMLButtonElement).disabled).toBe(true);
});
