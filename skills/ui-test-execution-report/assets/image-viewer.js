(() => {
  'use strict';
  if (document.getElementById('ui-image-viewer')) return;
  const dialog = document.createElement('dialog');
  dialog.id = 'ui-image-viewer';
  dialog.setAttribute('aria-labelledby', 'ui-viewer-title');
  dialog.innerHTML = '<div class="ui-viewer-toolbar"><h2 class="ui-viewer-title" id="ui-viewer-title">UI截图</h2>'
    + '<button type="button" data-viewer-action="fit-width" title="适应宽度">适应宽度</button>'
    + '<button type="button" data-viewer-action="fit" title="完整图片适应窗口">适应窗口</button>'
    + '<button type="button" data-viewer-action="actual" title="原始尺寸，1图片像素对应1 CSS像素">1:1</button>'
    + '<button type="button" data-viewer-action="out" aria-label="缩小" title="缩小">−</button>'
    + '<output class="ui-viewer-zoom" aria-live="polite">100%</output>'
    + '<button type="button" data-viewer-action="in" aria-label="放大" title="放大">+</button>'
    + '<button type="button" data-viewer-action="close" aria-label="关闭图片查看器" title="关闭">×</button></div>'
    + '<div class="ui-viewer-stage" tabindex="0" aria-label="图片滚动区域"><div class="ui-viewer-canvas"><img class="ui-viewer-picture" alt="" draggable="false"></div></div>'
    + '<div class="ui-viewer-footer"><p class="ui-viewer-error" role="alert"></p><details><summary class="ui-viewer-dimensions">证据路径与元数据</summary><p class="ui-viewer-path"></p><pre class="ui-viewer-metadata"></pre></details></div>';
  document.body.append(dialog);
  const picture = dialog.querySelector('.ui-viewer-picture');
  const stage = dialog.querySelector('.ui-viewer-stage');
  const canvas = dialog.querySelector('.ui-viewer-canvas');
  const zoomOutput = dialog.querySelector('.ui-viewer-zoom');
  const buttons = [...dialog.querySelectorAll('[data-viewer-action]')];
  let scale = 1, mode = 'fit-width', trigger = null, drag = null, generation = 0;
  let oldBodyOverflow = '', hadRootLock = false, ready = false;
  const clamp = n => Math.min(4, Math.max(.1, n));
  const setReady = value => {
    ready = value;
    buttons.forEach(b => { b.disabled = !ready && b.dataset.viewerAction !== 'close'; });
  };
  function render(nextScale, preserveCenter = false) {
    if (!ready) return;
    const oldWidth = picture.width || picture.naturalWidth;
    const oldHeight = picture.height || picture.naturalHeight;
    const centerX = (stage.scrollLeft + stage.clientWidth / 2) / oldWidth;
    const centerY = (stage.scrollTop + stage.clientHeight / 2) / oldHeight;
    scale = clamp(nextScale);
    const width = Math.max(1, Math.round(picture.naturalWidth * scale));
    const height = Math.max(1, Math.round(picture.naturalHeight * scale));
    picture.style.width = width + 'px';
    picture.style.height = height + 'px';
    canvas.style.width = width + 'px';
    canvas.style.height = height + 'px';
    zoomOutput.value = Math.round(scale * 100) + '%';
    zoomOutput.textContent = zoomOutput.value;
    buttons.forEach(b => b.setAttribute('aria-pressed', String(b.dataset.viewerAction === mode)));
    dialog.querySelector('[data-viewer-action="out"]').disabled = scale <= .1;
    dialog.querySelector('[data-viewer-action="in"]').disabled = scale >= 4;
    if (preserveCenter) {
      stage.scrollLeft = centerX * width - stage.clientWidth / 2;
      stage.scrollTop = centerY * height - stage.clientHeight / 2;
    } else { stage.scrollLeft = 0; stage.scrollTop = 0; }
  }
  function fit(kind) {
    if (!ready) return;
    mode = kind;
    const style = getComputedStyle(stage);
    const width = stage.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight) - 16;
    const height = stage.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom) - 16;
    if (kind === 'actual') render(1);
    else render(Math.min(1, width / picture.naturalWidth, kind === 'fit' ? height / picture.naturalHeight : Infinity));
  }
  function changeZoom(factor) { mode = 'custom'; render(scale * factor, true); }
  function open(button) {
    const img = button.querySelector('img');
    if (!img || !img.complete || !img.naturalWidth) return;
    trigger = button;
    dialog.querySelector('.ui-viewer-title').textContent = button.dataset.imageTitle || img.alt || 'UI截图';
    dialog.querySelector('.ui-viewer-path').textContent = button.dataset.imagePath || '';
    dialog.querySelector('.ui-viewer-metadata').textContent = button.dataset.imageMetadata || '{}';
    dialog.querySelector('.ui-viewer-error').textContent = '';
    dialog.querySelector('.ui-viewer-footer details').open = false;
    setReady(false);
    const openedGeneration = ++generation;
    picture.style.width = '1px'; picture.style.height = '1px';
    canvas.style.width = '1px'; canvas.style.height = '1px';
    oldBodyOverflow = document.body.style.overflow;
    hadRootLock = document.documentElement.classList.contains('ui-image-viewer-open');
    document.body.style.overflow = 'hidden';
    document.documentElement.classList.add('ui-image-viewer-open');
    dialog.showModal();
    const loaded = () => {
      if (openedGeneration !== generation || !dialog.open) return;
      setReady(true);
      dialog.querySelector('.ui-viewer-dimensions').textContent = '原图 ' + picture.naturalWidth + ' × ' + picture.naturalHeight + ' · 证据路径与元数据';
      requestAnimationFrame(() => fit('fit-width'));
    };
    picture.onload = loaded;
    picture.onerror = () => {
      if (openedGeneration !== generation) return;
      setReady(false);
      dialog.querySelector('.ui-viewer-error').textContent = '图片加载失败，请检查原始证据。';
    };
    picture.alt = img.alt || 'UI截图';
    picture.src = img.currentSrc || img.src;
    if (picture.complete && picture.naturalWidth) loaded();
    dialog.querySelector('[data-viewer-action="close"]').focus();
  }
  document.addEventListener('click', event => {
    const button = event.target.closest && event.target.closest('.ui-image-trigger');
    if (button && !dialog.open) { event.preventDefault(); open(button); }
  });
  dialog.addEventListener('click', event => {
    const button = event.target.closest('[data-viewer-action]');
    if (button) {
      const action = button.dataset.viewerAction;
      if (action === 'close') dialog.close();
      else if (action === 'in') changeZoom(1.25);
      else if (action === 'out') changeZoom(.8);
      else fit(action);
    } else if (event.target === dialog) dialog.close();
  });
  dialog.addEventListener('close', () => {
    ++generation; drag = null; setReady(false);
    stage.classList.remove('ui-dragging');
    document.body.style.overflow = oldBodyOverflow;
    if (!hadRootLock) document.documentElement.classList.remove('ui-image-viewer-open');
    if (trigger && trigger.isConnected) trigger.focus({preventScroll:true});
  });
  dialog.addEventListener('keydown', event => {
    if (event.key === '+' || event.key === '=') { event.preventDefault(); changeZoom(1.25); }
    if (event.key === '-') { event.preventDefault(); changeZoom(.8); }
    if (event.key === '0') { event.preventDefault(); fit('actual'); }
  });
  stage.addEventListener('wheel', event => {
    if (event.ctrlKey) { event.preventDefault(); changeZoom(event.deltaY < 0 ? 1.1 : 1 / 1.1); }
  }, {passive:false});
  stage.addEventListener('dblclick', () => fit(mode === 'actual' ? 'fit-width' : 'actual'));
  stage.addEventListener('pointerdown', event => {
    if (!ready || event.pointerType !== 'mouse' || event.button !== 0) return;
    drag = {x:event.clientX,y:event.clientY,left:stage.scrollLeft,top:stage.scrollTop};
    stage.setPointerCapture(event.pointerId); stage.classList.add('ui-dragging'); event.preventDefault();
  });
  stage.addEventListener('pointermove', event => {
    if (!drag) return;
    stage.scrollLeft = drag.left - (event.clientX - drag.x);
    stage.scrollTop = drag.top - (event.clientY - drag.y);
  });
  const finishDrag = () => {drag = null;stage.classList.remove('ui-dragging');};
  stage.addEventListener('pointerup', finishDrag);
  stage.addEventListener('pointercancel', finishDrag);
  new ResizeObserver(() => {
    if (dialog.open && ready && mode !== 'custom') fit(mode);
  }).observe(stage);
})();
