/**
 * Bundled `academic-figures` skill provider for DeepSeek Harness.
 *
 * The skill body (`SKILL.md`), its prompt library and reference material live
 * next to this file, so the installed package doubles as the DSH skill root.
 * Install with `dsh plugin add https://github.com/pordlm/py-academic-fig-skill`.
 *
 * @module academic-figures
 */

import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { BUNDLED_SKILL_RANK } from '@deepseek-ai/dsh-skill'

const PROVIDER_NAME = 'academic-figures'

const DESCRIPTION =
  '生成中文论文插图（数据图 / 框架图 / 场量图 / 流程图）统一的「简单高级框架风」：' +
  '白底墨线、低饱和强调色、细框刻度朝内、PNG+PDF 双出。用于画论文图表、复现或改造已有插图、' +
  '把数据变成可投稿的图、按期刊规格排版多面板图。当用户提到论文配图、论文插图、figure、图表美化、' +
  '框架图、技术路线图、消融实验图、热力图、雷达图、桑基图、ROC、混淆矩阵、响应面、覆盖图时使用。'

const SKILL_BODY_URL = new URL('./SKILL.md', import.meta.url)

const RESOURCE_BASE = {
  kind: 'directory',
  path: fileURLToPath(new URL('./', import.meta.url)),
}

const INVOCATION = { modelInvocable: true, userInvocable: true }

/** @type {import('@deepseek-ai/dsh-skill').SkillCandidate} */
const CANDIDATE = {
  name: PROVIDER_NAME,
  description: DESCRIPTION,
  invocation: INVOCATION,
  provider: PROVIDER_NAME,
  source: 'bundled',
  resourceBase: RESOURCE_BASE,
  rank: BUNDLED_SKILL_RANK,
  locator: SKILL_BODY_URL,
}

/** @type {import('@deepseek-ai/dsh-skill').SkillProvider} */
const provider = {
  name: PROVIDER_NAME,
  list: () => Promise.resolve([CANDIDATE]),
  async get() {
    return {
      name: CANDIDATE.name,
      description: CANDIDATE.description,
      invocation: CANDIDATE.invocation,
      provider: CANDIDATE.provider,
      source: CANDIDATE.source,
      resourceBase: RESOURCE_BASE,
      content: await readFile(SKILL_BODY_URL, 'utf8'),
    }
  },
}

/** Cordis plugin name. */
export const name = 'skill-academic-figures'

/** Service required by the bundled provider. */
export const inject = ['skills']

/** Register the bundled `academic-figures` provider on `ctx.skills`. */
export function apply(ctx) {
  ctx.skills.registerProvider(() => provider)
}