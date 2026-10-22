/** Pure helpers for leaderboard filter state and /dashboard/leaderboard query strings. */

export const GAMES = [
  { key: 'all', label: 'All Games' },
  { key: 'hoops', label: 'Hoops' },
  { key: 'laser', label: 'Laser Trap' },
  { key: 'climb', label: 'Climb' },
  { key: 'grid', label: 'Floor Is Lava' },
  { key: 'led_hex', label: 'LED Hexagon' },
]

export const PERIODS = [
  { key: 'today', label: 'Today' },
  { key: 'week', label: 'This Week' },
  { key: 'month', label: 'This Month' },
  { key: 'alltime', label: 'All Time' },
]

export const PLAY_MODES = [
  { key: '', label: 'All modes' },
  { key: 'quick_play', label: 'Quick Play' },
  { key: 'team_battle', label: 'Team Battle' },
  { key: 'tournament', label: 'Tournament' },
]

export const DIFFICULTIES = [
  { key: '', label: 'All difficulties' },
  { key: 'easy', label: 'Easy' },
  { key: 'normal', label: 'Normal' },
  { key: 'hard', label: 'Hard' },
]

export const TWO_CARD_OPTIONS = [
  { key: '', label: 'Any match type' },
  { key: 'true', label: 'Head-to-head only' },
  { key: 'false', label: 'Exclude head-to-head' },
]

/** @param {'public'|'admin'} variant */
export function defaultLeaderboardFilters(variant) {
  return {
    board: 'individual',
    period: variant === 'public' ? 'month' : 'alltime',
    game: 'all',
    companyId: '',
    groupId: '',
    tournamentId: '',
    playMode: '',
    minSize: '',
    maxSize: '',
    twoCard: '',
    includeArchived: false,
    difficulty: '',
    offset: 0,
    /** When false, team board may auto-apply minSize=2 */
    sizeTouched: false,
  }
}

export function boardToTournamentType(board) {
  return board === 'team' ? 'team' : 'solo'
}

/**
 * Build query string (no leading ?) for GET /dashboard/leaderboard.
 * @param {ReturnType<typeof defaultLeaderboardFilters>} state
 */
export function buildLeaderboardQuery(state, { limit = 20 } = {}) {
  const params = new URLSearchParams()
  params.set('game', state.game || 'all')
  params.set('period', state.period || 'alltime')
  params.set('limit', String(limit))
  params.set('board', state.board || 'individual')
  if (state.offset > 0) params.set('offset', String(state.offset))
  if (state.companyId) params.set('company_id', String(state.companyId))
  if (state.groupId) params.set('group_id', String(state.groupId))
  if (state.tournamentId) params.set('tournament_id', String(state.tournamentId))
  if (state.playMode) params.set('play_mode', state.playMode)
  if (state.minSize !== '' && state.minSize != null) params.set('min_size', String(state.minSize))
  if (state.maxSize !== '' && state.maxSize != null) params.set('max_size', String(state.maxSize))
  if (state.twoCard === 'true') params.set('two_card', 'true')
  if (state.twoCard === 'false') params.set('two_card', 'false')
  if (state.includeArchived) params.set('include_archived', 'true')
  if (state.difficulty) params.set('difficulty', state.difficulty)
  return params.toString()
}

/** Apply team-tab default min_size=2 when user has not set size manually. */
export function applyBoardTeamSizeDefault(prev, nextBoard) {
  const boardSwitch = { tournamentId: '', groupId: '', offset: 0 }
  if (nextBoard === 'team' && !prev.sizeTouched) {
    return { ...prev, ...boardSwitch, board: nextBoard, minSize: 2 }
  }
  if (nextBoard === 'individual') {
    const next = { ...prev, ...boardSwitch, board: nextBoard }
    if (!prev.sizeTouched) {
      next.minSize = ''
      next.maxSize = ''
    }
    return next
  }
  return { ...prev, ...boardSwitch, board: nextBoard }
}

export function formatTournamentWindow(t) {
  if (!t) return ''
  if (t.window_label) return t.window_label
  const s = t.starts_at
  const e = t.ends_at
  if (!s && !e) return 'All time'
  if (s && e) return `${s} – ${e}`
  if (s) return `From ${s}`
  return `Until ${e}`
}

export function formatPlayMode(mode) {
  if (!mode) return null
  const m = PLAY_MODES.find(p => p.key === mode)
  return m ? m.label : mode.replace(/_/g, ' ')
}
