// Read-only bridge to installed Pi. Never import extensions or install packages.
import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

try {
  const request = JSON.parse(readFileSync(0, 'utf8'));
  process.env.HOME = request.home;
  process.env.PI_CODING_AGENT_DIR = request.agentDir;
  process.env.PI_OFFLINE = '1';
  const core = join(request.piRoot, 'dist/core');
  const { SettingsManager } = await import(pathToFileURL(join(core, 'settings-manager.js')).href);
  const { DefaultPackageManager } = await import(pathToFileURL(join(core, 'package-manager.js')).href);
  if (typeof DefaultPackageManager.prototype.resolve !== 'function' ||
      typeof DefaultPackageManager.prototype.collectPackageResources !== 'function') {
    throw new Error('unsupported native Pi package-manager interface');
  }
  const makeManager = (global, project) => {
    const settings = SettingsManager.fromStorage({
      withLock(scope, callback) {
        const result = callback(JSON.stringify(scope === 'global' ? global : project));
        if (result !== undefined) throw new Error('read-only bridge attempted settings write');
      },
    }, { projectTrusted: true }); // Interpret selection; does not grant persistent trust.
    const pm = new DefaultPackageManager({
      cwd: request.project || request.home, agentDir: request.agentDir,
      settingsManager: settings, builtinExtensions: [],
    });
    // No configured commands (including malicious project npmCommand) may run here.
    pm.getLegacyGlobalNpmInstallPath = parsed => request.legacyRoot ? join(request.legacyRoot, parsed.name) : undefined;
    pm.runNpmCommand = pm.runNpmCommandSync = () => { throw new Error('inventory attempted installer execution'); };
    return pm;
  };
  const globalPM = makeManager(request.global, {});
  const projectPM = makeManager(request.global, request.projectSettings);
  const globalResolved = await globalPM.resolve(async () => 'skip');
  const projectResolved = request.project ? await projectPM.resolve(async () => 'skip') : { extensions: [] };
  const spec = record => typeof record === 'string' ? record : record.source;
  const records = settings => (settings.packages || []).filter(p => spec(p).startsWith('npm:'));
  const identity = source => globalPM.parseSource(source).name;
  const globalList = records(request.global), projectList = records(request.projectSettings);
  const scopedRecords = (list, scope) => globalPM.dedupePackages(list.map(pkg => ({ pkg, scope }))).map(e => e.pkg);
  const globalRecords = new Map(scopedRecords(globalList, 'user').map(p => [identity(spec(p)), p]));
  const projectRecords = new Map(scopedRecords(projectList, 'project').map(p => [identity(spec(p)), p]));
  const states = Object.create(null);
  const candidate = (scope, name) => Object.hasOwn(request.candidates[scope] || {}, name) ? request.candidates[scope][name] : `npm:${name}`;
  for (const name of request.identities) {
    const g = globalRecords.get(name), p = projectRecords.get(name);
    const scopeState = async (scope, record, resolved) => {
      const inherits = scope === 'project' && (!record || (typeof record === 'object' && record.autoload === false)) && !!g;
      const selected = inherits ? g : record;
      const source = selected ? spec(selected) : candidate(scope, name);
      const pm = scope === 'global' ? globalPM : projectPM;
      const storageScope = scope === 'global' || inherits ? 'user' : 'project';
      const root = pm.getInstalledPath(source, storageScope);
      let version = null, metadata = null;
      if (root && existsSync(join(root, 'package.json'))) {
        try { metadata = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8')); version = metadata.version || null; } catch {}
      }
      const compatible = !!root && await pm.installedNpmMatchesConfiguredVersion(pm.parseSource(source), root);
      const scopeSource = record ? spec(record) : candidate(scope, name);
      const managed = pm.getManagedNpmInstallPath(pm.parseSource(scopeSource), scope === 'global' ? 'user' : 'project');
      const scopeRoot = existsSync(managed) ? managed : scope === 'global' ? root : null;
      let scopeVersion = null;
      if (scopeRoot) { try { scopeVersion = JSON.parse(readFileSync(join(scopeRoot, 'package.json'), 'utf8')).version || null; } catch {} }
      const scopeCompatible = !!scopeRoot && await pm.installedNpmMatchesConfiguredVersion(pm.parseSource(scopeSource), scopeRoot);
      const entries = resolved.extensions.filter(e => e.metadata.origin === 'package' &&
        e.metadata.source.startsWith('npm:') && identity(e.metadata.source) === name)
        .map(e => ({ path: e.path, enabled: e.enabled }));
      const resources = [];
      if (root && compatible) {
        const accumulator = pm.createAccumulator();
        pm.collectPackageResources(root, accumulator, undefined, { source, scope: storageScope, origin: 'package', baseDir: root, packageRoot: root });
        for (const e of pm.toResolvedPaths(accumulator).extensions) resources.push(e.path);
      }
      return { record: record || null, source, root: root || null, version, metadata,
        compatible, scope_root: scopeRoot || null, scope_version: scopeVersion, scope_compatible: scopeCompatible,
        ambiguous: (scope === 'global' ? globalList : projectList).filter(p => identity(spec(p)) === name).length > 1 ||
          (inherits && globalList.filter(p => identity(spec(p)) === name).length > 1),
        configured: !!selected, missing: !!selected && !compatible,
        mode: inherits ? (record && Object.hasOwn(record, 'extensions') ? 'override' : 'inherit') : record ? 'owned' : 'available',
        entries, resources,
        external: !!root && !!request.legacyRoot && root === join(request.legacyRoot, name) &&
          root !== pm.getManagedNpmInstallPath(pm.parseSource(source), storageScope) };
    };
    states[name] = {
      global: await scopeState('global', g, globalResolved),
      project: request.project ? await scopeState('project', p, projectResolved) : null,
    };
  }
  process.stdout.write(JSON.stringify(states));
} catch (error) {
  process.stderr.write(`Native Pi inventory: ${error.message}\n`);
  process.exitCode = 1;
}
