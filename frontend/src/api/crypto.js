import JSEncrypt from 'jsencrypt'

let publicKeyPromise = null

async function loadPublicKey() {
  if (!publicKeyPromise) {
    publicKeyPromise = fetch('/api/auth/publicKey')
      .then((response) => response.json())
      .then((body) => {
        const data = body.data || {}
        return data.publicKeyPem || ''
      })
      .catch(() => {
        publicKeyPromise = null
        return ''
      })
  }
  return publicKeyPromise
}

export async function encrypt(value) {
  const pem = await loadPublicKey()
  if (!pem) throw new Error('无法获取加密公钥')
  const encryptor = new JSEncrypt()
  encryptor.setPublicKey(pem)
  const result = encryptor.encrypt(String(value))
  if (!result) throw new Error('密码加密失败')
  return result
}
