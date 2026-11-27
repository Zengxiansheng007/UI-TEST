/** Open a top-level Chromium window within the fixture's existing, authorized context. */
async function targetInfo(context, page) {
  const session = await context.newCDPSession(page);
  try {
    const {targetInfo} = await session.send('Target.getTargetInfo');
    return targetInfo;
  } finally {
    await session.detach();
  }
}

async function openContinuationWindow(original) {
  const context = original.context();
  const control = await context.browser().newBrowserCDPSession();
  let created;
  try {
    const source = await targetInfo(context, original);
    if (!source.browserContextId) throw new Error('Original browser context unavailable');
    const originalWindow = await control.send('Browser.getWindowForTarget', {targetId:source.targetId});
    const creation = control.send('Target.createTarget', {
      url:'about:blank', browserContextId:source.browserContextId, newWindow:true
    }).then(target => { created = target; return target; });
    // CDP and Playwright signal creation independently. Accept only our exact target in this context.
    const [,page] = await Promise.all([creation, context.waitForEvent('page', {
      timeout:10000,
      predicate:async candidate => {
        const [wanted,actual] = await Promise.all([creation, targetInfo(context, candidate)]);
        return actual.targetId === wanted.targetId && actual.browserContextId === source.browserContextId;
      }
    })]);
    const opened = await control.send('Browser.getWindowForTarget', created);
    if (!Number.isInteger(opened.windowId) || !Number.isInteger(originalWindow.windowId) ||
        opened.windowId === originalWindow.windowId) throw new Error('Distinct browser window unavailable');
    return {page, evidence:{original_window_id:originalWindow.windowId, window_id:opened.windowId}};
  } catch (error) {
    if (created) await control.send('Target.closeTarget', created).catch(() => {}); // Only the new blank target.
    throw error;
  } finally {
    await control.detach();
  }
}

module.exports = {openContinuationWindow};
