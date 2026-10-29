// @vitest-environment jsdom
import {it,expect,afterEach} from 'vitest';
import {render,screen,cleanup} from '@testing-library/react';
import {CreditOverview,type CreditUsage} from './Credits';
afterEach(cleanup);
it('shows separate expiring balances and a trial countdown',()=>{
 const usage={unlimited:false,available_seconds:21600,trial_seconds:5400,free_seconds:0,paid_seconds:16200,eligible:true,trial_expires_at:new Date(Date.now()+86400000).toISOString(),next_refresh_at:new Date(Date.now()+86400000).toISOString(),paid_grants:[]} as unknown as CreditUsage;
 render(<CreditOverview usage={usage}/>);
 expect(screen.getByText('360')).toBeTruthy();
 expect(screen.getByText('90')).toBeTruthy();
 expect(screen.getByText('270')).toBeTruthy();
 expect(screen.getByText(/Expires in/)).toBeTruthy();
 expect(screen.getByText(/60 minutes each month/)).toBeTruthy();
});
