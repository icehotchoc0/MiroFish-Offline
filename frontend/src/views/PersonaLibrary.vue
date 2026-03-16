<template>
  <div class="persona-library-container">
    <!-- Top Navigation Bar -->
    <nav class="navbar" :style="s.navbar">
      <div :style="s.navBrand" @click="$router.push('/')" class="nav-brand-link">MIROFISH OFFLINE</div>
      <div :style="s.navLinks">
        <router-link to="/" :style="s.navLink">홈</router-link>
        <router-link to="/personas" :style="s.navLinkActive">페르소나 라이브러리</router-link>
      </div>
    </nav>

    <div :style="s.mainContent">
      <!-- Header -->
      <div :style="s.pageHeader">
        <div>
          <div :style="s.tagRow">
            <span :style="s.orangeTag">페르소나 관리</span>
          </div>
          <h1 :style="s.pageTitle">페르소나 라이브러리</h1>
          <p :style="s.pageDesc">시뮬레이션에 사용할 에이전트 페르소나를 관리합니다. AI를 활용하여 자동으로 생성하거나 직접 만들 수 있습니다.</p>
        </div>
        <button :style="s.createBtn" @click="openCreate">
          + 새 페르소나 만들기
        </button>
      </div>

      <div :style="s.divider"></div>

      <!-- Loading -->
      <div v-if="loading" :style="s.statusMessage">
        <span :style="s.loadingDot">...</span> 페르소나 목록을 불러오는 중...
      </div>

      <!-- Error -->
      <div v-else-if="error" :style="s.errorBanner">
        {{ error }}
        <button :style="s.retryBtn" @click="fetchPersonas">다시 시도</button>
      </div>

      <!-- Empty State -->
      <div v-else-if="personas.length === 0" :style="s.emptyState">
        <div :style="s.emptyIcon">?</div>
        <div :style="s.emptyTitle">아직 페르소나가 없습니다</div>
        <div :style="s.emptyDesc">새 페르소나를 만들어보세요.</div>
        <button :style="s.createBtnSmall" @click="openCreate">+ 새 페르소나 만들기</button>
      </div>

      <!-- Card Grid -->
      <div v-else :style="s.cardGrid">
        <div
          v-for="persona in personas"
          :key="persona.id"
          :style="s.card"
          @click="openEdit(persona)"
          class="persona-card"
        >
          <div :style="s.cardHeader">
            <div :style="s.cardName">{{ persona.name }}</div>
            <button
              :style="s.deleteBtn"
              @click.stop="confirmDelete(persona)"
              title="삭제"
            >x</button>
          </div>
          <div :style="s.cardMeta">
            <span v-if="persona.profession" :style="s.metaTag">{{ persona.profession }}</span>
            <span v-if="persona.mbti" :style="s.metaTagMbti">{{ persona.mbti }}</span>
            <span v-if="persona.age" :style="s.metaTag">{{ persona.age }}세</span>
          </div>
          <div v-if="persona.bio" :style="s.cardBio">{{ truncate(persona.bio, 100) }}</div>
          <div :style="s.cardFooter">
            <span v-if="persona.country" :style="s.footerText">{{ persona.country }}</span>
            <span v-if="persona.interested_topics && persona.interested_topics.length" :style="s.footerText">
              {{ persona.interested_topics.slice(0, 3).join(', ') }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Editor Modal -->
    <PersonaEditor
      v-if="showEditor"
      :persona="editingPersona"
      :mode="editorMode"
      @save="handleSave"
      @cancel="closeEditor"
    />

    <!-- Delete Confirmation -->
    <div v-if="showDeleteConfirm" class="persona-editor-overlay" @click.self="showDeleteConfirm = false">
      <div :style="s.confirmDialog">
        <div :style="s.confirmTitle">페르소나 삭제</div>
        <div :style="s.confirmText">
          "{{ deletingPersona?.name }}" 페르소나를 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.
        </div>
        <div :style="s.confirmActions">
          <button :style="s.cancelBtn" @click="showDeleteConfirm = false">취소</button>
          <button :style="s.confirmDeleteBtn" @click="handleDelete" :disabled="deleting">
            {{ deleting ? '삭제 중...' : '삭제' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { listPersonas, createPersona, updatePersona, deletePersona as deletePersonaApi } from '../api/persona'
import PersonaEditor from '../components/PersonaEditor.vue'

const mono = 'JetBrains Mono, monospace'
const sans = 'Space Grotesk, Noto Sans SC, system-ui, sans-serif'

const personas = ref([])
const loading = ref(false)
const error = ref('')

const showEditor = ref(false)
const editorMode = ref('create')
const editingPersona = ref(null)

const showDeleteConfirm = ref(false)
const deletingPersona = ref(null)
const deleting = ref(false)

const truncate = (text, max) => {
  if (!text) return ''
  return text.length > max ? text.slice(0, max) + '...' : text
}

const fetchPersonas = async () => {
  loading.value = true
  error.value = ''
  try {
    const res = await listPersonas()
    personas.value = res.data || res.personas || res || []
    if (!Array.isArray(personas.value)) personas.value = []
  } catch (err) {
    error.value = '페르소나 목록을 불러오지 못했습니다.'
    console.error('Fetch personas error:', err)
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  editingPersona.value = null
  editorMode.value = 'create'
  showEditor.value = true
}

const openEdit = (persona) => {
  editingPersona.value = { ...persona }
  editorMode.value = 'edit'
  showEditor.value = true
}

const closeEditor = () => {
  showEditor.value = false
  editingPersona.value = null
}

const handleSave = async (data) => {
  try {
    if (editorMode.value === 'create') {
      await createPersona(data)
    } else {
      await updatePersona(editingPersona.value.id, data)
    }
    closeEditor()
    await fetchPersonas()
  } catch (err) {
    console.error('Save persona error:', err)
  }
}

const confirmDelete = (persona) => {
  deletingPersona.value = persona
  showDeleteConfirm.value = true
}

const handleDelete = async () => {
  if (!deletingPersona.value || deleting.value) return
  deleting.value = true
  try {
    await deletePersonaApi(deletingPersona.value.id)
    showDeleteConfirm.value = false
    deletingPersona.value = null
    await fetchPersonas()
  } catch (err) {
    console.error('Delete persona error:', err)
  } finally {
    deleting.value = false
  }
}

onMounted(fetchPersonas)

const s = reactive({
  navbar: {
    height: '60px',
    background: '#000',
    color: '#fff',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '0 40px'
  },
  navBrand: {
    fontFamily: mono,
    fontWeight: '800',
    letterSpacing: '1px',
    fontSize: '1.2rem',
    cursor: 'pointer'
  },
  navLinks: {
    display: 'flex',
    alignItems: 'center',
    gap: '24px'
  },
  navLink: {
    color: '#999',
    textDecoration: 'none',
    fontFamily: mono,
    fontSize: '0.85rem',
    fontWeight: '500'
  },
  navLinkActive: {
    color: '#fff',
    textDecoration: 'none',
    fontFamily: mono,
    fontSize: '0.85rem',
    fontWeight: '700'
  },
  mainContent: {
    maxWidth: '1200px',
    margin: '0 auto',
    padding: '50px 40px'
  },
  pageHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: '30px'
  },
  tagRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '15px',
    marginBottom: '12px'
  },
  orangeTag: {
    background: '#FF4500',
    color: '#fff',
    padding: '4px 10px',
    fontFamily: mono,
    fontWeight: '700',
    letterSpacing: '1px',
    fontSize: '0.75rem'
  },
  pageTitle: {
    fontSize: '2.5rem',
    fontWeight: '520',
    margin: '0 0 10px 0',
    letterSpacing: '-1px',
    color: '#000'
  },
  pageDesc: {
    color: '#666',
    fontSize: '0.95rem',
    lineHeight: '1.6',
    maxWidth: '600px',
    margin: '0'
  },
  createBtn: {
    background: '#000',
    color: '#fff',
    border: 'none',
    padding: '14px 24px',
    fontFamily: mono,
    fontWeight: '700',
    fontSize: '0.9rem',
    cursor: 'pointer',
    letterSpacing: '0.5px',
    whiteSpace: 'nowrap',
    marginTop: '30px'
  },
  divider: {
    borderTop: '1px solid #EAEAEA',
    marginBottom: '40px'
  },
  statusMessage: {
    textAlign: 'center',
    padding: '60px 0',
    color: '#999',
    fontFamily: mono,
    fontSize: '0.9rem'
  },
  loadingDot: {
    color: '#FF4500',
    fontWeight: '700'
  },
  errorBanner: {
    padding: '16px 20px',
    background: '#FFF5F2',
    border: '1px solid #FF4500',
    color: '#FF4500',
    fontSize: '0.9rem',
    fontFamily: mono,
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center'
  },
  retryBtn: {
    background: '#FF4500',
    color: '#fff',
    border: 'none',
    padding: '6px 14px',
    fontFamily: mono,
    fontSize: '0.8rem',
    cursor: 'pointer'
  },
  emptyState: {
    textAlign: 'center',
    padding: '80px 0'
  },
  emptyIcon: {
    width: '48px',
    height: '48px',
    border: '1px solid #EAEAEA',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    margin: '0 auto 16px',
    fontSize: '1.5rem',
    color: '#CCC',
    fontFamily: mono
  },
  emptyTitle: {
    fontSize: '1.1rem',
    fontWeight: '600',
    color: '#333',
    marginBottom: '8px'
  },
  emptyDesc: {
    fontSize: '0.9rem',
    color: '#999',
    marginBottom: '24px'
  },
  createBtnSmall: {
    background: '#000',
    color: '#fff',
    border: 'none',
    padding: '10px 20px',
    fontFamily: mono,
    fontWeight: '600',
    fontSize: '0.85rem',
    cursor: 'pointer'
  },
  cardGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
    gap: '20px'
  },
  card: {
    border: '1px solid #EAEAEA',
    padding: '24px',
    background: '#fff',
    cursor: 'pointer',
    transition: 'border-color 0.15s',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px'
  },
  cardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start'
  },
  cardName: {
    fontSize: '1.15rem',
    fontWeight: '600',
    color: '#000'
  },
  deleteBtn: {
    background: 'none',
    border: '1px solid #EAEAEA',
    width: '28px',
    height: '28px',
    cursor: 'pointer',
    fontSize: '0.9rem',
    color: '#999',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: mono,
    flexShrink: '0'
  },
  cardMeta: {
    display: 'flex',
    gap: '8px',
    flexWrap: 'wrap'
  },
  metaTag: {
    background: '#F5F5F5',
    padding: '3px 8px',
    fontSize: '0.75rem',
    fontFamily: mono,
    color: '#666'
  },
  metaTagMbti: {
    background: '#000',
    color: '#fff',
    padding: '3px 8px',
    fontSize: '0.75rem',
    fontFamily: mono,
    fontWeight: '600'
  },
  cardBio: {
    fontSize: '0.85rem',
    color: '#666',
    lineHeight: '1.5'
  },
  cardFooter: {
    display: 'flex',
    gap: '12px',
    fontSize: '0.75rem',
    color: '#AAA',
    fontFamily: mono,
    borderTop: '1px solid #F5F5F5',
    paddingTop: '10px',
    marginTop: 'auto'
  },
  footerText: {},
  // Confirm dialog
  confirmDialog: {
    background: '#fff',
    border: '1px solid #EAEAEA',
    padding: '30px',
    width: '400px',
    maxWidth: '90vw',
    fontFamily: sans
  },
  confirmTitle: {
    fontSize: '1.1rem',
    fontWeight: '600',
    marginBottom: '12px',
    color: '#000'
  },
  confirmText: {
    fontSize: '0.9rem',
    color: '#666',
    lineHeight: '1.6',
    marginBottom: '24px'
  },
  confirmActions: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '12px'
  },
  cancelBtn: {
    background: '#fff',
    border: '1px solid #EAEAEA',
    padding: '10px 20px',
    fontFamily: mono,
    fontSize: '0.85rem',
    cursor: 'pointer',
    color: '#666'
  },
  confirmDeleteBtn: {
    background: '#FF4500',
    color: '#fff',
    border: 'none',
    padding: '10px 20px',
    fontFamily: mono,
    fontSize: '0.85rem',
    fontWeight: '600',
    cursor: 'pointer'
  }
})
</script>

<style scoped>
.persona-library-container {
  min-height: 100vh;
  background: #fff;
}

.nav-brand-link {
  cursor: pointer;
}

.persona-card:hover {
  border-color: #CCC !important;
}

.persona-editor-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
</style>
