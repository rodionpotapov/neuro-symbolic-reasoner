let examples = [];
window.addEventListener('DOMContentLoaded', () => {
    fetch('/api/examples').then(r=>r.json()).then(data => {examples=data;});
});
function loadExample(idx) {
    if (!examples[idx]) return;
    document.getElementById('taskInput').value = examples[idx].text;
}
function solveProblem() {
    const task = document.getElementById('taskInput').value.trim();
    const solveBtn = document.getElementById('solveBtn');
    if (!task) { alert('Введите задачу!'); return; }
    solveBtn.disabled = true; solveBtn.textContent = '⏳ Решаю...';
    fetch('/api/solve', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({task})
    }).then(r=>r.json()).then(data => {
        document.getElementById('formulasOutput').textContent =
            (data.formulas||[]).map(f => '- '+f).join('\n') + (data.goal ? '\nЦель: '+data.goal : '');
        document.getElementById('proofResult').textContent = data.proven ? '✓ Доказано' : '✗ Не доказано';
        document.getElementById('stepsCount').textContent = (data.proof_steps||[]).length +' шагов';
        document.getElementById('proofSteps').textContent = (data.proof_steps||[]).join('\n');
        document.getElementById('explanationOutput').textContent = data.explanation||'';
        if (data.error) {
            document.getElementById('errorBlock').style.display='';
            document.getElementById('errorOutput').textContent = data.error;
        } else {
            document.getElementById('errorBlock').style.display='none';
        }
    }).catch(err=>{
        document.getElementById('errorBlock').style.display='';
        document.getElementById('errorOutput').textContent='Ошибка: '+err;
    }).finally(_=>{solveBtn.disabled=false;solveBtn.textContent='🚀 Решить задачу';});
}
