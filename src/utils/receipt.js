import QRCode from 'qrcode'
import { money, dateTime } from './format'

// Render a downloadable demo receipt locally; the payment URL stays inside the real QR.
export async function receiptPng({ restaurantName, qr, url }) {
  const canvas=document.createElement('canvas')
  canvas.width=640
  const ctx=canvas.getContext('2d')
  if(!ctx) throw new Error('Браузер не поддерживает создание изображения чека.')
  const lines=(text,maxWidth)=>{
    const result=[]; let line=''
    for(const char of String(text)){
      if(ctx.measureText(line+char).width>maxWidth){result.push(line);line=char}else line+=char
    }
    if(line)result.push(line)
    return result
  }
  ctx.font='bold 28px sans-serif'
  const nameLines=lines(restaurantName||'Ресторан',540)
  ctx.font='20px monospace'
  const numberLines=lines(qr.receipt?`Чек № ${qr.receipt.number}`:'Предчек · демонстрация',540)
  canvas.height=960+(nameLines.length-1)*38+(numberLines.length-1)*28
  ctx.fillStyle='#fff';ctx.fillRect(0,0,canvas.width,canvas.height)
  ctx.textAlign='center';ctx.fillStyle='#202621'
  let y=65
  ctx.font='bold 28px sans-serif'
  for(const line of nameLines){ctx.fillText(line,320,y);y+=38}
  ctx.font='16px monospace';ctx.fillText('ДЕМОНСТРАЦИОННЫЙ ПРЕДЧЕК',320,y+15);y+=65
  ctx.font='20px monospace'
  for(const line of numberLines){ctx.fillText(line,320,y);y+=28}
  ctx.font='18px monospace';ctx.fillText(dateTime(qr.createdAt||new Date().toISOString()),320,y+10);y+=55
  function divider(){ctx.beginPath();ctx.strokeStyle='#adb3ac';ctx.setLineDash([5,5]);ctx.moveTo(40,y);ctx.lineTo(600,y);ctx.stroke();ctx.setLineDash([]);y+=40}
  divider()
  ctx.textAlign='left';ctx.font='21px sans-serif';ctx.fillText('Сумма заказа',45,y)
  ctx.textAlign='right';ctx.font='bold 25px sans-serif';ctx.fillText(qr.receipt?money(qr.receipt.billAmount,qr.currency):'Не указана',595,y);y+=45
  divider()
  ctx.textAlign='center';ctx.font='bold 24px sans-serif';ctx.fillText('Оставить чаевые',320,y);y+=40
  ctx.font='18px sans-serif';ctx.fillText('Сканируйте QR и выберите сотрудника',320,y);y+=20
  const qrCanvas=document.createElement('canvas')
  await QRCode.toCanvas(qrCanvas,url,{width:310,margin:4,errorCorrectionLevel:'M',color:{dark:'#000000',light:'#ffffff'}})
  ctx.drawImage(qrCanvas,165,y,310,310);y+=345
  ctx.font='17px sans-serif';ctx.fillText('Чаевые не входят в сумму заказа.',320,y);y+=31
  ctx.fillText('Регистрация гостя не нужна.',320,y);y+=48
  ctx.font='16px monospace';ctx.fillText('Не является кассовым чеком.',320,y)
  return canvas.toDataURL('image/png')
}
