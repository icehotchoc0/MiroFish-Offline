<template>
  <div class="persona-editor-overlay" @click.self="$emit('cancel')">
    <div class="persona-editor" :style="s.editor">
      <div class="editor-header" :style="s.header">
        <h2 :style="s.headerTitle">{{ mode === 'create' ? '새 페르소나 만들기' : '페르소나 편집' }}</h2>
        <button :style="s.closeBtn" @click="$emit('cancel')">x</button>
      </div>

      <!-- AI 생성 섹션 -->
      <div :style="s.aiSection">
        <label :style="s.label">자유 텍스트로 페르소나 설명</label>
        <div :style="s.aiRow">
          <textarea
            v-model="aiDescription"
            :style="s.aiTextarea"
            placeholder="예: 30대 후반 IT 스타트업 대표, ENTJ, 기술 트렌드에 민감하고 공격적인 투자 성향..."
            rows="3"
            :disabled="generating"
          ></textarea>
          <button
            :style="[s.aiBtn, generating ? s.aiBtnDisabled : {}]"
            @click="handleGenerate"
            :disabled="generating || !aiDescription.trim()"
          >
            <span v-if="!generating">AI 생성</span>
            <span v-else>생성 중...</span>
          </button>
        </div>
        <div v-if="aiError" :style="s.errorText">{{ aiError }}</div>
      </div>

      <div :style="s.divider"></div>

      <!-- 폼 필드 -->
      <div :style="s.formBody">
        <div :style="s.formGrid">
          <!-- 이름 -->
          <div :style="s.fieldFull">
            <label :style="s.label">이름 <span :style="s.required">*</span></label>
            <input v-model="form.name" :style="s.input" placeholder="페르소나 이름" />
          </div>

          <!-- 나이, 성별 -->
          <div :style="s.fieldHalf">
            <label :style="s.label">나이</label>
            <input v-model.number="form.age" :style="s.input" type="number" min="1" max="120" placeholder="30" />
          </div>
          <div :style="s.fieldHalf">
            <label :style="s.label">성별</label>
            <select v-model="form.gender" :style="s.input">
              <option value="">선택</option>
              <option value="male">남성</option>
              <option value="female">여성</option>
              <option value="other">기타</option>
            </select>
          </div>

          <!-- 국가, MBTI -->
          <div :style="s.fieldHalf">
            <label :style="s.label">국가</label>
            <input v-model="form.country" :style="s.input" placeholder="대한민국" />
          </div>
          <div :style="s.fieldHalf">
            <label :style="s.label">MBTI</label>
            <input v-model="form.mbti" :style="s.input" placeholder="ENTJ" maxlength="4" />
          </div>

          <!-- 직업 -->
          <div :style="s.fieldFull">
            <label :style="s.label">직업</label>
            <input v-model="form.profession" :style="s.input" placeholder="소프트웨어 엔지니어" />
          </div>

          <!-- 소개 -->
          <div :style="s.fieldFull">
            <label :style="s.label">소개 (bio)</label>
            <textarea v-model="form.bio" :style="s.textarea" placeholder="이 페르소나에 대한 간략한 소개" rows="2"></textarea>
          </div>

          <!-- 페르소나 설명 -->
          <div :style="s.fieldFull">
            <label :style="s.label">페르소나 상세 설명</label>
            <textarea v-model="form.persona" :style="s.textarea" placeholder="이 페르소나의 성격, 가치관, 행동 패턴 등을 상세하게 기술하세요" rows="3"></textarea>
          </div>

          <!-- 관심 주제 -->
          <div :style="s.fieldFull">
            <label :style="s.label">관심 주제 (쉼표로 구분)</label>
            <input v-model="topicsInput" :style="s.input" placeholder="기술, 경제, 정치, 환경" />
          </div>

          <!-- 슬라이더들 -->
          <div :style="s.fieldFull">
            <label :style="s.label">의견 편향도: {{ form.opinion_bias.toFixed(2) }}</label>
            <input type="range" v-model.number="form.opinion_bias" min="0" max="1" step="0.01" :style="s.slider" />
            <div :style="s.sliderLabels">
              <span>중립적 (0)</span>
              <span>강한 편향 (1)</span>
            </div>
          </div>

          <div :style="s.fieldFull">
            <label :style="s.label">영향력 수준: {{ form.influence_level.toFixed(2) }}</label>
            <input type="range" v-model.number="form.influence_level" min="0" max="1" step="0.01" :style="s.slider" />
            <div :style="s.sliderLabels">
              <span>낮음 (0)</span>
              <span>높음 (1)</span>
            </div>
          </div>

          <div :style="s.fieldFull">
            <label :style="s.label">반응 속도: {{ form.reaction_speed.toFixed(2) }}</label>
            <input type="range" v-model.number="form.reaction_speed" min="0" max="1" step="0.01" :style="s.slider" />
            <div :style="s.sliderLabels">
              <span>느림 (0)</span>
              <span>빠름 (1)</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 에러 메시지 -->
      <div v-if="saveError" :style="s.errorBanner">{{ saveError }}</div>

      <!-- 버튼 -->
      <div :style="s.footer">
        <button :style="s.cancelBtn" @click="$emit('cancel')">취소</button>
        <button
          :style="[s.saveBtn, (!form.name.trim() || saving) ? s.saveBtnDisabled : {}]"
          @click="handleSave"
          :disabled="!form.name.trim() || saving"
        >
          {{ saving ? '저장 중...' : '저장' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, watch, computed } from 'vue'
import { generatePersona } from '../api/persona'

const mono = 'JetBrains Mono, monospace'
const sans = 'Space Grotesk, Noto Sans SC, system-ui, sans-serif'

const props = defineProps({
  persona: { type: Object, default: null },
  mode: { type: String, default: 'create' }
})

const emit = defineEmits(['save', 'cancel'])

const defaultForm = () => ({
  name: '',
  age: null,
  gender: '',
  country: '',
  mbti: '',
  profession: '',
  bio: '',
  persona: '',
  interested_topics: [],
  opinion_bias: 0.5,
  influence_level: 0.5,
  reaction_speed: 0.5
})

const form = reactive(props.persona ? { ...defaultForm(), ...props.persona } : defaultForm())

const topicsInput = ref(
  Array.isArray(form.interested_topics) ? form.interested_topics.join(', ') : ''
)

watch(topicsInput, (val) => {
  form.interested_topics = val.split(',').map(t => t.trim()).filter(Boolean)
})

const aiDescription = ref('')
const generating = ref(false)
const aiError = ref('')
const saving = ref(false)
const saveError = ref('')

const handleGenerate = async () => {
  if (!aiDescription.value.trim() || generating.value) return
  generating.value = true
  aiError.value = ''
  try {
    const res = await generatePersona(aiDescription.value)
    const data = res.data || res.persona || res
    if (data) {
      const fields = ['name', 'age', 'gender', 'country', 'mbti', 'profession', 'bio', 'persona']
      fields.forEach(f => { if (data[f] !== undefined) form[f] = data[f] })
      if (data.interested_topics) {
        form.interested_topics = Array.isArray(data.interested_topics) ? data.interested_topics : [data.interested_topics]
        topicsInput.value = form.interested_topics.join(', ')
      }
      if (data.opinion_bias !== undefined) form.opinion_bias = Number(data.opinion_bias)
      if (data.influence_level !== undefined) form.influence_level = Number(data.influence_level)
      if (data.reaction_speed !== undefined) form.reaction_speed = Number(data.reaction_speed)
    }
  } catch (err) {
    aiError.value = 'AI 생성에 실패했습니다. 다시 시도해주세요.'
    console.error('Persona generation error:', err)
  } finally {
    generating.value = false
  }
}

const handleSave = () => {
  if (!form.name.trim() || saving.value) return
  saving.value = true
  saveError.value = ''
  const data = { ...form }
  if (data.age) data.age = Number(data.age)
  emit('save', data)
  // Parent will handle the async; reset saving if needed
  setTimeout(() => { saving.value = false }, 2000)
}

const s = reactive({
  editor: {
    position: 'relative',
    background: '#fff',
    width: '680px',
    maxWidth: '95vw',
    maxHeight: '90vh',
    overflowY: 'auto',
    border: '1px solid #EAEAEA',
    fontFamily: sans
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '24px 30px 20px',
    borderBottom: '1px solid #EAEAEA'
  },
  headerTitle: {
    fontSize: '1.3rem',
    fontWeight: '600',
    margin: '0',
    color: '#000'
  },
  closeBtn: {
    background: 'none',
    border: '1px solid #EAEAEA',
    width: '32px',
    height: '32px',
    cursor: 'pointer',
    fontSize: '1rem',
    color: '#999',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: mono
  },
  aiSection: {
    padding: '20px 30px'
  },
  aiRow: {
    display: 'flex',
    gap: '12px',
    alignItems: 'flex-start'
  },
  aiTextarea: {
    flex: '1',
    border: '1px solid #EAEAEA',
    padding: '12px',
    fontFamily: sans,
    fontSize: '0.9rem',
    resize: 'vertical',
    outline: 'none',
    background: '#FAFAFA',
    lineHeight: '1.5'
  },
  aiBtn: {
    background: '#000',
    color: '#fff',
    border: 'none',
    padding: '12px 20px',
    fontFamily: mono,
    fontSize: '0.85rem',
    fontWeight: '600',
    cursor: 'pointer',
    whiteSpace: 'nowrap',
    letterSpacing: '0.5px',
    minWidth: '90px'
  },
  aiBtnDisabled: {
    opacity: '0.4',
    cursor: 'not-allowed'
  },
  errorText: {
    color: '#FF4500',
    fontSize: '0.8rem',
    marginTop: '8px',
    fontFamily: mono
  },
  divider: {
    borderTop: '1px solid #EAEAEA',
    margin: '0 30px'
  },
  formBody: {
    padding: '20px 30px'
  },
  formGrid: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '16px'
  },
  fieldFull: {
    width: '100%',
    display: 'flex',
    flexDirection: 'column',
    gap: '6px'
  },
  fieldHalf: {
    width: 'calc(50% - 8px)',
    display: 'flex',
    flexDirection: 'column',
    gap: '6px'
  },
  label: {
    fontSize: '0.8rem',
    fontWeight: '600',
    color: '#333',
    fontFamily: mono
  },
  required: {
    color: '#FF4500'
  },
  input: {
    border: '1px solid #EAEAEA',
    padding: '10px 12px',
    fontSize: '0.9rem',
    fontFamily: sans,
    outline: 'none',
    background: '#fff',
    width: '100%',
    boxSizing: 'border-box'
  },
  textarea: {
    border: '1px solid #EAEAEA',
    padding: '10px 12px',
    fontSize: '0.9rem',
    fontFamily: sans,
    outline: 'none',
    background: '#fff',
    resize: 'vertical',
    lineHeight: '1.5',
    width: '100%',
    boxSizing: 'border-box'
  },
  slider: {
    width: '100%',
    cursor: 'pointer',
    accentColor: '#000'
  },
  sliderLabels: {
    display: 'flex',
    justifyContent: 'space-between',
    fontSize: '0.7rem',
    color: '#999',
    fontFamily: mono
  },
  errorBanner: {
    margin: '0 30px',
    padding: '10px 14px',
    background: '#FFF5F2',
    border: '1px solid #FF4500',
    color: '#FF4500',
    fontSize: '0.85rem',
    fontFamily: mono
  },
  footer: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '12px',
    padding: '20px 30px',
    borderTop: '1px solid #EAEAEA'
  },
  cancelBtn: {
    background: '#fff',
    border: '1px solid #EAEAEA',
    padding: '10px 24px',
    fontFamily: mono,
    fontSize: '0.85rem',
    cursor: 'pointer',
    color: '#666'
  },
  saveBtn: {
    background: '#000',
    color: '#fff',
    border: 'none',
    padding: '10px 24px',
    fontFamily: mono,
    fontSize: '0.85rem',
    fontWeight: '600',
    cursor: 'pointer',
    letterSpacing: '0.5px'
  },
  saveBtnDisabled: {
    opacity: '0.4',
    cursor: 'not-allowed'
  }
})
</script>

<style scoped>
.persona-editor-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.persona-editor::-webkit-scrollbar {
  width: 4px;
}

.persona-editor::-webkit-scrollbar-thumb {
  background: #ccc;
}
</style>
