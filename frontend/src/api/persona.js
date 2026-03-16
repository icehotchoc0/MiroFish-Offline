import service, { requestWithRetry } from './index'

/**
 * 페르소나 목록 조회
 * @returns {Promise}
 */
export const listPersonas = () => {
  return service.get('/api/personas')
}

/**
 * 페르소나 생성
 * @param {Object} data - 페르소나 데이터
 * @returns {Promise}
 */
export const createPersona = (data) => {
  return requestWithRetry(() => service.post('/api/personas', data), 3, 1000)
}

/**
 * 페르소나 상세 조회
 * @param {string} id - 페르소나 ID
 * @returns {Promise}
 */
export const getPersona = (id) => {
  return service.get(`/api/personas/${id}`)
}

/**
 * 페르소나 수정
 * @param {string} id - 페르소나 ID
 * @param {Object} data - 수정할 데이터
 * @returns {Promise}
 */
export const updatePersona = (id, data) => {
  return requestWithRetry(() => service.put(`/api/personas/${id}`, data), 3, 1000)
}

/**
 * 페르소나 삭제
 * @param {string} id - 페르소나 ID
 * @returns {Promise}
 */
export const deletePersona = (id) => {
  return service.delete(`/api/personas/${id}`)
}

/**
 * AI로 페르소나 자동 생성
 * @param {string} description - 자유 텍스트 설명
 * @returns {Promise}
 */
export const generatePersona = (description) => {
  return requestWithRetry(
    () => service.post('/api/personas/generate', { description }),
    3,
    1000
  )
}
