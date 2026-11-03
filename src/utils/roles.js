export const roleNames = { employee: 'Сотрудник', merchant: 'Администратор ресторана', admin: 'Администратор платформы' }
export const homeForRole = role => role === 'employee' ? '/app/me' : role === 'admin' ? '/app/admin' : '/app'
