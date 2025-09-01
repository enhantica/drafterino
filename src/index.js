#!/usr/bin/env node
const fs = require('fs');
const core = require('@actions/core');
const yaml = require('js-yaml');
const semver = require('semver');
const { execSync } = require('child_process');

function getLatestTag() {
  try {
    const tags = execSync('git tag --merged HEAD --sort=-creatordate', { encoding: 'utf-8' })
      .trim()
      .split('\n');
    console.log('🔖 Reachable tags:\n', tags.join('\n'));
    for (const tag of tags) {
      const cleaned = tag.replace(/^v/, '').split('.post')[0];
      if (semver.valid(cleaned)) return tag;
    }
  } catch {
    // fallthrough
  }
  return '0.0.0';
}

function getMergedPRs(token) {
  const eventPath = process.env.GITHUB_EVENT_PATH;
  if (!eventPath || !fs.existsSync(eventPath)) {
    console.log('⚠️ No event payload found, skipping PR lookup.');
    return [];
  }

  const event = JSON.parse(fs.readFileSync(eventPath, 'utf8'));
  const repo = event.repository || {};
  const owner = repo.owner?.login;
  const repoName = repo.name;

  if (!(owner && repoName && token)) {
    console.log('⚠️ Missing GitHub context for API call.');
    return [];
  }

  const prevTag = getLatestTag();
  const logCmd = prevTag === '0.0.0' ? 'git log --pretty=format:%H' : `git log ${prevTag}..HEAD --pretty=format:%H`;

  let commitShas = [];
  try {
    commitShas = execSync(logCmd, { encoding: 'utf8' }).trim().split('\n');
  } catch (e) {
    console.log(`⚠️ Failed to run git log: ${e.message}`);
    return [];
  }

  const seenPRs = {};
  const headers = {
    Authorization: `Bearer ${token}`,
    Accept: 'application/vnd.github.groot-preview+json',
  };

  return Promise.all(commitShas.map(async sha => {
    const url = `https://api.github.com/repos/${owner}/${repoName}/commits/${sha}/pulls`;
    const res = await fetch(url, { headers });
    if (res.ok) {
      const prs = await res.json();
      prs.forEach(pr => {
        if (pr.merged_at) seenPRs[pr.number] = pr;
      });
    }
  })).then(() => {
    const mergedPRs = Object.values(seenPRs);
    console.log('🧾 PRs merged after the latest tag (all branches):');
    mergedPRs.forEach(pr =>
      console.log(` - ${pr.title} (#${pr.number}) - SHA: ${pr.merge_commit_sha}`));
    return mergedPRs;
  });
}

function determineBump(prs, cfg) {
  const groups = {
    major: cfg['major-bump-labels'] || [],
    minor: cfg['minor-bump-labels'] || [],
    patch: cfg['patch-bump-labels'] || [],
    post:  cfg['post-bump-labels'] || [],
  };

  console.log('🧪 Bump label groups from config:', groups);
  const found = Object.fromEntries(Object.keys(groups).map(k => [k, false]));

  prs.forEach(pr => {
    const labels = pr.labels.map(l => l.name);
    for (const [key, patterns] of Object.entries(groups)) {
      if (patterns.some(p => labels.includes(p))) found[key] = true;
    }
  });

  if (found.major) return 'major';
  if (found.minor) return 'minor';
  if (found.patch) return 'patch';
  if (found.post) return 'post';
  return cfg['default-bump'] || 'post';
}

function bumpVersion(prev, type) {
  const base = prev.replace(/^v/, '').split('.post')[0];
  let next = semver.parse(base);
  if (!next) throw new Error(`Invalid previous version: ${prev}`);

  switch (type) {
    case 'major': return next.inc('major');
    case 'minor': return next.inc('minor');
    case 'patch': return next.inc('patch');
    case 'post': {
      const match = prev.match(/\.post(\d+)/);
      const n = match ? parseInt(match[1]) + 1 : 1;
      return `${base}.post${n}`;
    }
    default: throw new Error(`Unknown bump type: ${type}`);
  }
}

function substitutePlaceholders(cfg, version) {
  ['tag', 'title'].forEach(k => {
    if (typeof cfg[k] === 'string') {
      cfg[k] = cfg[k].replace('$COMPUTED_VERSION', version);
    }
  });
}

function generateNotes(prs, cfg) {
  const sections = cfg['release-notes'] || [];
  const grouped = {};

  prs.forEach(pr => {
    const labels = pr.labels.map(l => l.name);
    const title = pr.title;
    const number = pr.number;
    sections.forEach(sec => {
      if (sec.labels.some(l => labels.includes(l))) {
        grouped[sec.title] ||= [];
        grouped[sec.title].push(`- ${title} (#${number})`);
      }
    });
  });

  return sections.map(sec => {
    const entries = grouped[sec.title] || [];
    return entries.length ? `## ${sec.title}\n${entries.join('\n')}` : '';
  }).filter(Boolean).join('\n\n') || '_No notable changes._';
}

async function run() {
  try {
    const rawConfig = core.getInput('config');
    const rawFiles = core.getInput('files') || '';
    const token = process.env.GITHUB_TOKEN;

    if (!rawConfig) throw new Error('CONFIG input not provided');
    const cfg = yaml.load(rawConfig);

    console.log('🔧 Loaded config:\n', yaml.dump(cfg));

    const prev = getLatestTag();
    console.log('🔖 Latest tag:', prev);

    const prs = await getMergedPRs(token);
    console.log(`📦 Merged PRs: ${prs.length}`);

    const bump = determineBump(prs, cfg);
    console.log('🔧 Selected bump type:', bump);

    const version = bumpVersion(prev, bump);
    console.log('🧮 Computed new version:', version);

    substitutePlaceholders(cfg, version);

    const notes = generateNotes(prs, cfg);
    console.log('📝 Generated release notes:\n', notes);

    const files = rawFiles.split('\n').map(f => f.trim()).filter(Boolean);
    files.forEach(f => {
      if (!fs.existsSync(f)) {
        console.warn(`⚠️ File not found: ${f}`);
      } else {
        console.log(`📄 Found file: ${f}`);
      }
    });

    core.setOutput('version', version);
    core.setOutput('tag_name', cfg.tag);
    core.setOutput('release_name', cfg.title);
    core.setOutput('release_notes', notes);
    core.setOutput('files', files.join('\n'));
  } catch (err) {
    core.setFailed(`❌ ${err.message}`);
  }
}

run();
