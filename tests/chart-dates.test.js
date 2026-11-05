import { test } from 'node:test'
import assert from 'node:assert/strict'
import { calendarDate, buildDailySeries } from '../src/utils/dates.js'

test('Moscow chart at 00:30 keeps values under their displayed calendar day',()=>{
 const rows=buildDailySeries({now:'2026-11-04T21:30:00Z',timeZone:'Europe/Moscow',seriesTimeZone:'Europe/Moscow',days:3,locale:'en-US',dailySeries:[
  {date:'2026-11-03',total:'5'},{date:'2026-11-04',total:'10'},{date:'2026-11-05',total:'20'},
 ]})
 assert.deepEqual(rows.map(r=>[r.key,r.date,r.value]),[['2026-11-03','Nov 3',5],['2026-11-04','Nov 4',10],['2026-11-05','Nov 5',20]])
})

test('UTC-8 and UTC+14 use their own current day without ISO conversion shifts',()=>{
 const west=buildDailySeries({now:'2026-11-05T07:30:00Z',timeZone:'America/Los_Angeles',days:2,payments:[
  {status:'success',createdAt:'2026-11-04T07:59:59Z',amount:10},
  {status:'success',createdAt:'2026-11-04T08:00:00Z',amount:20},
  {status:'success',createdAt:'2026-11-05T07:00:00Z',amount:30},
 ]})
 assert.deepEqual(west.map(r=>[r.key,r.value]),[['2026-11-03',10],['2026-11-04',50]])
 const east=buildDailySeries({now:'2026-11-04T10:30:00Z',timeZone:'Pacific/Kiritimati',days:1,payments:[{status:'success',createdAt:'2026-11-04T10:00:00Z',amount:7}]})
 assert.equal(east[0].key,'2026-11-05');assert.equal(east[0].value,7)
})

test('server aggregates in another timezone are rebuilt from payment instants',()=>{
 const rows=buildDailySeries({now:'2026-11-04T21:30:00Z',timeZone:'Europe/Moscow',seriesTimeZone:'UTC',days:2,dailySeries:[{period:'2026-11-04T00:00:00Z',total:30}],payments:[
  {status:'success',createdAt:'2026-11-04T20:59:59Z',amount:10},
  {status:'success',createdAt:'2026-11-04T21:00:00Z',amount:20},
  {status:'declined',createdAt:'2026-11-04T21:00:00Z',amount:100},
 ]})
 assert.deepEqual(rows.map(r=>[r.key,r.value]),[['2026-11-04',10],['2026-11-05',20]])
})

test('calendar categories cross daylight-saving transitions without missing or repeated days',()=>{
 const spring=buildDailySeries({now:'2026-03-10T00:00:00Z',timeZone:'America/Los_Angeles',days:4})
 assert.deepEqual(spring.map(r=>r.key),['2026-03-06','2026-03-07','2026-03-08','2026-03-09'])
 const fall=buildDailySeries({now:'2026-11-03T02:00:00Z',timeZone:'America/Los_Angeles',days:4,payments:[
  {status:'success',createdAt:'2026-11-01T08:30:00Z',amount:10},
  {status:'success',createdAt:'2026-11-01T09:30:00Z',amount:20},
 ]})
 assert.deepEqual(fall.map(r=>r.key),['2026-10-30','2026-10-31','2026-11-01','2026-11-02'])
 assert.equal(fall.find(r=>r.key==='2026-11-01').value,30)
})

test('month/year boundaries and invalid timestamps never invent calendar dates',()=>{
 assert.equal(calendarDate('2027-01-01T00:30:00+03:00','Europe/Moscow'),'2027-01-01')
 const rows=buildDailySeries({now:'2027-01-01T00:30:00+03:00',timeZone:'Europe/Moscow',days:3,payments:[
  {status:'success',createdAt:null,amount:10},{status:'success',createdAt:'invalid',amount:20},
 ]})
 assert.deepEqual(rows.map(r=>r.key),['2026-12-30','2026-12-31','2027-01-01'])
 assert.equal(rows.reduce((sum,r)=>sum+r.value,0),0)
})
