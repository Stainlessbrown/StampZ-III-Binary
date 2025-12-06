# Deprecation Warnings and Future Upgrades

**Last Updated:** December 6, 2024

## Current Issues (Resolved)

### ✅ pkg_resources Deprecation
- **Status:** FIXED (Dec 6, 2024)
- **Removal Date:** 2025-11-30
- **Issue:** `pkg_resources` is deprecated and causes PyInstaller bundling issues
- **Solution Applied:** Added `jaraco.*` hidden imports to work around until removal
- **Future Action:** Monitor for setuptools <81 compatibility

## Upcoming Deprecations to Watch

### 1. Python 3.12 EOL Considerations
**Current:** Python 3.12 (secure until October 2028)
- **Action Needed:** None immediate
- **Timeline:** Consider Python 3.13+ adoption in 2026-2027

### 2. NumPy Version Compatibility
**Current:** numpy==2.2.4 (latest stable)
- **Status:** ✅ Already on latest major version (2.x)
- **Watch For:** NumPy 2.x deprecated APIs
- **Action:** Monitor deprecation warnings in numpy 2.x releases

### 3. Pillow (PIL) Updates
**Current:** Pillow==10.4.0
- **Latest Stable:** 11.x series available
- **Action Needed:** Consider upgrading to Pillow 11.x
- **Risk:** Low - Pillow maintains good backward compatibility
- **Timeline:** Q1 2025

### 4. Matplotlib Changes
**Current:** matplotlib==3.9.2
- **Latest:** 3.9.x series
- **Watch For:** Deprecated color names, API changes
- **Action:** Stay on 3.9.x series, monitor 4.0 roadmap
- **Timeline:** Matplotlib 4.0 expected 2025

### 5. pandas API Evolution
**Current:** pandas==2.2.3
- **Status:** pandas 2.x is stable
- **Watch For:** FutureWarnings in pandas operations
- **Action:** Review code for deprecated pandas methods
- **Timeline:** pandas 3.0 planned for 2025-2026

### 6. scikit-learn Updates
**Current:** scikit-learn==1.5.2
- **Latest:** 1.6.x available
- **Watch For:** Deprecated estimator parameters
- **Action:** Consider upgrading to 1.6.x
- **Timeline:** Safe to upgrade now

### 7. OpenCV Version
**Current:** opencv-python==4.11.0.86
- **Status:** Latest 4.x series
- **Action:** None needed - OpenCV 4.x is stable
- **Timeline:** OpenCV 5.x not yet released

### 8. PyInstaller Compatibility
**Current:** pyinstaller==6.3.0
- **Latest:** 6.x series
- **Watch For:** macOS code signing changes, Python 3.13 support
- **Action:** Stay updated with 6.x series
- **Timeline:** Continuous monitoring

## Planned Deprecations in Dependencies

### High Priority (Action Required Soon)

#### 1. pkg_resources → importlib.metadata
- **Deadline:** November 30, 2025
- **Impact:** HIGH - Current workaround in place
- **Action Plan:**
  1. ✅ Added jaraco hidden imports (Dec 2024)
  2. 🔲 Monitor setuptools updates
  3. 🔲 Migrate to importlib.metadata if needed (Q3 2025)
  4. 🔲 Test with setuptools >=81 before deadline

#### 2. Pillow 10.x → 11.x Migration
- **Timeline:** Q1 2025
- **Impact:** LOW - Mostly backward compatible
- **Action Plan:**
  1. Test with Pillow 11.x in development
  2. Check for deprecated image modes
  3. Update requirements.txt
  4. Full regression test

#### 3. matplotlib 3.x → 4.0 (Future)
- **Timeline:** Est. 2025
- **Impact:** MEDIUM - API changes expected
- **Action Plan:**
  1. Monitor matplotlib 4.0 release notes
  2. Test beta versions when available
  3. Update color specifications if needed
  4. Review deprecated APIs

### Medium Priority (Plan Ahead)

#### 4. pandas 2.x → 3.0 (Future)
- **Timeline:** 2025-2026
- **Impact:** MEDIUM
- **Watch For:**
  - Deprecated indexing methods
  - Changes to groupby behavior
  - FutureWarnings in current code
- **Action:** Address FutureWarnings as they appear

#### 5. Python 3.12 → 3.13 Migration
- **Timeline:** 2025-2026
- **Impact:** LOW to MEDIUM
- **Considerations:**
  - PyInstaller 3.13 support
  - Dependency compatibility
  - Performance improvements
- **Action:** Test in 2025 when ecosystem stabilizes

### Low Priority (Monitor Only)

#### 6. tkinter API Stability
- **Status:** Part of Python stdlib, very stable
- **Impact:** VERY LOW
- **Action:** None needed - tkinter rarely breaks

#### 7. colorspacious Updates
- **Current:** 1.1.2 (last updated 2020)
- **Status:** Stable but unmaintained
- **Impact:** LOW - core functionality stable
- **Action:** Monitor for alternatives if needed

## Deprecation Monitoring Strategy

### Monthly Checks
- [ ] Review GitHub Dependabot alerts
- [ ] Check PyPI for security advisories
- [ ] Run: `pip list --outdated`

### Quarterly Reviews
- [ ] Test with latest stable versions in dev environment
- [ ] Review deprecation warnings: `python -W default::DeprecationWarning main.py`
- [ ] Check major dependency roadmaps

### Annual Planning
- [ ] Major version upgrade strategy
- [ ] Python version upgrade timeline
- [ ] Dependency EOL review

## Testing for Deprecations

### Command to Check for Warnings:
```bash
# Run app with all deprecation warnings visible
python -W default::DeprecationWarning main.py

# Check specific module
python -W default::DeprecationWarning -c "import numpy; import pandas; import matplotlib"

# Save warnings to file
python -W default::DeprecationWarning main.py 2> deprecation_warnings.txt
```

### CI/CD Integration:
Consider adding to GitHub Actions:
```yaml
- name: Check for deprecation warnings
  run: |
    python -W error::DeprecationWarning -c "import numpy; import pandas; import matplotlib" || true
```

## Current Dependency Status Summary

| Package | Current | Latest | Upgrade Priority | Notes |
|---------|---------|--------|------------------|-------|
| numpy | 2.2.4 | 2.2.4 | ✅ Up-to-date | - |
| Pillow | 10.4.0 | 11.x | 🟡 Medium | Test 11.x in Q1 2025 |
| opencv-python | 4.11.0.86 | 4.11.x | ✅ Recent | - |
| matplotlib | 3.9.2 | 3.9.x | ✅ Current | Watch for 4.0 |
| pandas | 2.2.3 | 2.2.x | ✅ Current | - |
| scikit-learn | 1.5.2 | 1.6.x | 🟢 Low | Can upgrade now |
| pyinstaller | 6.3.0 | 6.x | ✅ Recent | Monitor for 7.0 |
| plotly | 5.24.1 | 5.x | ✅ Current | - |

**Legend:**
- ✅ No action needed
- 🟢 Optional upgrade available
- 🟡 Upgrade recommended
- 🔴 Urgent action required

## Recommendations

### Immediate (Q4 2024 - Q1 2025)
1. ✅ **DONE:** Fix pkg_resources/jaraco issue
2. 🔲 Test with Pillow 11.x
3. 🔲 Upgrade scikit-learn to 1.6.x (optional)
4. 🔲 Run deprecation warning scan

### Short Term (Q2-Q3 2025)
1. Monitor setuptools updates for pkg_resources removal
2. Plan matplotlib 4.0 migration if released
3. Address any FutureWarnings from pandas

### Long Term (2026+)
1. Plan Python 3.13 migration
2. Consider pandas 3.0 upgrade when stable
3. Regular security updates for all dependencies

## Additional Resources

- [Python Release Schedule](https://peps.python.org/pep-0693/)
- [NumPy Roadmap](https://numpy.org/neps/)
- [Pandas Roadmap](https://pandas.pydata.org/about/roadmap.html)
- [Matplotlib Release Notes](https://matplotlib.org/stable/users/release_notes.html)
- [PyInstaller Compatibility](https://pyinstaller.org/en/stable/CHANGES.html)

---

**Next Review:** March 2025
