# Pending Optimizations

## Summary

Based on `OPTIMIZATION_OPPORTUNITIES.md`, here's what has been completed and what remains:

---

## ✅ Completed (Phase 1 + Some Phase 2)

### Phase 1 - High Priority ✅
1. ✅ Pre-compile regex patterns in `HTMLPostProcessor`
2. ✅ Combine multiple `find_all("cite")` calls
3. ✅ Optimize ZIP file extraction
4. ✅ Add parallel asset conversion

### Phase 2 - Medium Priority (Partially Complete)
1. ✅ Cache file metadata
2. ✅ Optimize string operations
3. ✅ Switch to `lxml` parser
4. ❌ **PENDING**: Implement caching for package checks

---

## ❌ Pending Optimizations

### High Priority (Production)

#### 1. Package Availability Caching - 🟡 MEDIUM
**Location**: `app/services/package_manager.py` (`check_package_availability`)

**Issue**: 
- `check_package_availability()` calls `tlmgr info` for each package individually
- Same packages checked multiple times across different conversions
- Each check is a subprocess call (expensive)

**Current Code** (lines 135-175):
```python
def check_package_availability(self, packages: list[str]) -> dict[str, bool]:
    for package in packages:
        result = run_command_safely(
            ["tlmgr", "info", "--only-installed", package], timeout=30
        )
        availability[package] = result.returncode == 0
```

**Optimization**:
- Add cache dictionary: `self._package_cache: dict[str, tuple[bool, float]]`
- Cache TTL: 5-10 minutes (packages don't change frequently)
- Batch check multiple packages if possible

**Estimated Improvement**: 50-80% faster for repeated package checks

---

### Medium Priority

#### 2. Optimize `_fix_equation_tables` Method - 🟡 MEDIUM
**Location**: `app/services/html_post.py` (lines 576-916)

**Issue**:
- Multiple `find_all()` calls within loops
- Repeated element lookups
- Could use pre-compiled patterns for class matching

**Current Issues**:
- Line 586-588: `soup.find_all("table", class_=self.equation_table_pattern)` - OK (uses pre-compiled)
- Line 595: `tbody.find_all("tr", class_=self.equation_row_pattern)` - OK (uses pre-compiled)
- Lines 610-614: Multiple `find()` calls in loop - could cache results
- Lines 668-673: Multiple `find_all()` calls - could combine

**Optimization**:
- Cache element lookups within loops
- Combine multiple `find_all()` calls where possible
- Pre-compile any remaining regex patterns

**Estimated Improvement**: 20-30% faster equation table processing

---

#### 3. Multiple File Reads - 🟡 MEDIUM
**Location**: Various services

**Issue**:
- HTML files read for parsing, then again for validation
- SVG files read for validation, then again for optimization
- Same file content loaded multiple times

**Optimization**:
- Read once, cache content, pass to multiple processors
- Use file content caching with TTL

**Estimated Improvement**: 10-20% reduction in I/O operations

---

#### 4. Multiple BeautifulSoup Traversals - 🟡 MEDIUM
**Location**: `app/services/html_post.py` (`process_html` method)

**Issue**:
- HTML parsed once but processed through multiple stages:
  - Cleaning
  - Validation
  - Asset conversion
  - Enhancement
  - Optimization
- Each stage may traverse the entire DOM

**Current**: Using lxml parser (faster), but still multiple traversals

**Optimization**:
- Combine operations where possible
- Single-pass approach for related operations
- Cache intermediate results

**Estimated Improvement**: 15-25% faster for large HTML files

---

#### 5. In-Memory Storage Growth - 🟡 MEDIUM (Production: 🔴 HIGH)
**Location**: `app/api/conversion.py`

**Issue**:
- Global `_conversion_storage` dictionary grows unbounded
- Memory usage increases over time
- Not persistent across restarts

**Current Mitigation**: Cleanup thread exists

**Optimization**:
- Implement LRU cache with size limits
- Use weak references where appropriate
- **Production**: Migrate to Redis or PostgreSQL

**Priority**: Critical for production deployment

**Estimated Improvement**: Prevents memory leaks, better scalability

---

### Low Priority

#### 6. List Comprehensions vs Loops - 🟢 LOW
**Location**: Various files

**Issue**: Some loops could be replaced with more efficient list comprehensions

**Example**: `app/services/file_discovery.py` line 315

**Estimated Improvement**: Minor (<5%)

---

#### 7. Dictionary Lookups - 🟢 LOW
**Location**: Various files

**Issue**: Some dictionary lookups use `.get()` with defaults that could be optimized

**Estimated Improvement**: Minor (<5%)

---

#### 8. Large HTML Files Loaded Entirely - 🟢 LOW
**Location**: `app/services/html_post.py`

**Issue**: Entire HTML file loaded into memory (line 96-97)

**Optimization**:
- Use streaming parsing for very large files (>50MB)
- Process in chunks where possible
- Memory-mapped files for read-only operations

**Estimated Improvement**: Better memory usage for very large files

---

#### 9. HTML Processing Stages Parallelization - 🟢 LOW
**Location**: `app/services/html_post.py` (`process_html`)

**Issue**: Some independent operations could run in parallel

**Optimization**: Parallelize asset discovery and HTML cleaning

**Estimated Improvement**: 10-15% faster for documents with many assets

---

#### 10. Performance Monitoring - 🟢 LOW
**Location**: All services

**Issue**: No performance metrics or profiling

**Optimization**:
- Add performance metrics (processing time per stage)
- Monitor memory usage
- Track file I/O operations
- Use `cProfile` for profiling

**Estimated Improvement**: Better visibility into bottlenecks

---

## Implementation Priority

### Next Steps (Recommended Order)

1. **Package Availability Caching** (Medium Priority)
   - High impact, relatively easy to implement
   - Estimated: 1-2 hours

2. **Optimize `_fix_equation_tables`** (Medium Priority)
   - Moderate impact, straightforward
   - Estimated: 2-3 hours

3. **Multiple File Reads Caching** (Medium Priority)
   - Moderate impact, requires careful design
   - Estimated: 3-4 hours

4. **In-Memory Storage Optimization** (High Priority for Production)
   - Critical for production, requires testing
   - Estimated: 4-6 hours

5. **Performance Monitoring** (Low Priority)
   - Good for long-term optimization
   - Estimated: 4-6 hours

---

## Notes

- All pending optimizations maintain backward compatibility
- Test each optimization with real-world documents
- Profile before and after to measure actual impact
- Some optimizations may require trade-offs (e.g., memory vs. speed)

---

## Quick Reference

| Optimization | Priority | Impact | Effort | Status |
|--------------|----------|--------|--------|--------|
| Package availability caching | Medium | High | Low | ❌ Pending |
| Equation table optimization | Medium | Medium | Low | ❌ Pending |
| Multiple file reads caching | Medium | Medium | Medium | ❌ Pending |
| Multiple DOM traversals | Medium | Medium | Medium | ❌ Pending |
| In-memory storage (production) | High | High | High | ❌ Pending |
| List comprehensions | Low | Low | Low | ❌ Pending |
| Dictionary lookups | Low | Low | Low | ❌ Pending |
| Large file streaming | Low | Low | High | ❌ Pending |
| Performance monitoring | Low | Medium | Medium | ❌ Pending |
