#include "decisions.h"
#include "menu.h"          // reuse renderMenuBackground / drawButtonRect / GameScreenState
#include "text_sprites.h"
#include "turn_system.h"
#include <string.h>
#include <stdio.h>
#include "province_owners.h"
#include "flags.h"
#include "province_cores.h"
#include "province_owners.h"
#include "formable_cores.h"


#define MAX_RUNTIME_CORES 128

#define BGR15(r,g,b) (0x8000 | ((b) << 10) | ((g) << 5) | (r))
#define SCREEN_W     256

CountryPolitics country_politics_runtime[COUNTRY_POLITICS_COUNT];
bool decision_taken[DECISION_COUNT];
bool countryExists[COUNTRY_COUNT];

// -1 = this country has never taken this decision
static int decisionLastTakenTurn[DECISION_COUNT][COUNTRY_COUNT];

extern bool needsRedraw; // from main.cpp

static ProvinceCore runtimeCores[MAX_RUNTIME_CORES];
static int runtimeCoreCount = 0;


int getRuntimeCoreCount() { return runtimeCoreCount; }
const ProvinceCore* getRuntimeCore(int index) { return &runtimeCores[index]; }

static void initCountryExistence()
{
    for (int i = 0; i < COUNTRY_COUNT; i++)
        countryExists[i] = !countries[i].is_formable;
}

static void transferAllProvinces(unsigned char fromCountry, unsigned char toCountry)
{
    for (int p = 0; p < PROVINCE_OWNER_COUNT; p++)
        if (province_owners[p] == fromCountry)
            province_owners[p] = toCountry;
}

static void addRuntimeCore(int pid, unsigned char cid)
{
    if (pid < 0 || pid >= PROVINCE_OWNER_COUNT) return;
    if (runtimeCoreCount >= MAX_RUNTIME_CORES) return;
    runtimeCores[runtimeCoreCount].province_id = pid;
    runtimeCores[runtimeCoreCount].country_id  = cid;
    runtimeCoreCount++;
}

//---------------------------------------------
// INIT
//---------------------------------------------

void initDecisionsSystem()
{
    memcpy(country_politics_runtime, country_politics, sizeof(country_politics_runtime));
    memset(decision_taken, 0, sizeof(decision_taken));
	
	 initCountryExistence();

    for (int i = 0; i < DECISION_COUNT; i++)
        for (int c = 0; c < COUNTRY_COUNT; c++)
            decisionLastTakenTurn[i][c] = -1;
}

//---------------------------------------------
// CONDITION EVALUATION — postfix/RPN stack machine
//---------------------------------------------

#define MAX_COND_STACK 32

bool evaluateConditionProgram(unsigned short offset, unsigned short length, unsigned char countryId)
{
    if (length == CONDITION_ALWAYS_TRUE)
        return true;

    // Defensive: catches a stale build where decisions_data.h/.c drifted out of sync
    if ((int)offset + (int)length > CONDITION_POOL_COUNT)
        return false;

    bool stack[MAX_COND_STACK];
    int sp = 0;

    for (unsigned short i = 0; i < length; i++)
    {
        const ConditionInstr* instr = &condition_pool[offset + i];
        bool result = false;

        switch (instr->opcode)
        {
            case CONDOP_AND:
                if (sp < 2) return false;
                result = stack[sp-2] && stack[sp-1];
                sp -= 2;
                break;

            case CONDOP_OR:
                if (sp < 2) return false;
                result = stack[sp-2] || stack[sp-1];
                sp -= 2;
                break;

            case CONDOP_NOT:
                if (sp < 1) return false;
                result = !stack[sp-1];
                sp -= 1;
                break;

            case CONDOP_COUNTRY_IS:
                result = (countryId == instr->operand1);
                break;

            case CONDOP_STABILITY_GE:
                result = (countryId < COUNTRY_POLITICS_COUNT) &&
                         (country_politics_runtime[countryId].stability >= instr->operand1);
                break;

            case CONDOP_STABILITY_LE:
                result = (countryId < COUNTRY_POLITICS_COUNT) &&
                         (country_politics_runtime[countryId].stability <= instr->operand1);
                break;

            case CONDOP_SUPPORT_GE:
                result = (countryId < COUNTRY_POLITICS_COUNT) &&
                         (country_politics_runtime[countryId].ideology_support[instr->operand1] >= instr->operand2);
                break;

            case CONDOP_SUPPORT_LE:
                result = (countryId < COUNTRY_POLITICS_COUNT) &&
                         (country_politics_runtime[countryId].ideology_support[instr->operand1] <= instr->operand2);
                break;

            case CONDOP_RULING_IS:
                result = (countryId < COUNTRY_POLITICS_COUNT) &&
                         (country_politics_runtime[countryId].ruling_ideology == instr->operand1);
                break;

            case CONDOP_CONTROLS_PROVINCE:
                result = (instr->operand1 >= 0 && instr->operand1 < PROVINCE_OWNER_COUNT) &&
                         (province_owners[instr->operand1] == countryId);
                break;

            case CONDOP_DECISION_TAKEN:
                result = (instr->operand1 >= 0 && instr->operand1 < DECISION_COUNT) &&
                         decision_taken[instr->operand1];
                break;
        }

        if (sp >= MAX_COND_STACK) return false; // malformed program — bail rather than overflow
        stack[sp++] = result;
    }

    return sp > 0 ? stack[sp-1] : false;
}

//---------------------------------------------
// AVAILABILITY / VISIBILITY / COOLDOWN
//---------------------------------------------

bool isDecisionVisible(int decisionIdx, unsigned char countryId)
{
    if (decisionIdx < 0 || decisionIdx >= DECISION_COUNT) return false;
    const Decision* d = &decisions[decisionIdx];
    return evaluateConditionProgram(d->visibility_offset, d->visibility_length, countryId);
}

bool isDecisionAvailable(int decisionIdx, unsigned char countryId)
{
    if (decisionIdx < 0 || decisionIdx >= DECISION_COUNT) return false;
    if (countryId >= COUNTRY_COUNT) return false;
    const Decision* d = &decisions[decisionIdx];

    if (!evaluateConditionProgram(d->availability_offset, d->availability_length, countryId))
        return false;

    int lastTurn = decisionLastTakenTurn[decisionIdx][countryId];
    if (lastTurn < 0)
        return true; // never taken by this country — conditions already passed above

    if (d->cooldown_turns == DECISION_ONCE_ONLY)
        return false; // already taken once, ever

    return (CURRENT_TURN.current_turn - lastTurn) >= d->cooldown_turns;
}

//---------------------------------------------
// EFFECTS
//---------------------------------------------

// ADD_SUPPORT rebalancing policy: clamp the target ideology to 0-100, then
// redistribute the opposite delta proportionally across the other three so
// the total stays at ~100. This is ONE reasonable policy, not the only
// valid one — revisit if decisions end up wanting a different feel (e.g.
// always pulling from the single largest ideology instead of a blend).
static void applySupportDelta(unsigned char countryId, int targetIdeology, int delta)
{
    unsigned char* support = country_politics_runtime[countryId].ideology_support;

    int oldVal = support[targetIdeology];
    int newVal = oldVal + delta;
    if (newVal < 0) newVal = 0;
    if (newVal > 100) newVal = 100;
    int actualDelta = newVal - oldVal;
    support[targetIdeology] = (unsigned char)newVal;

    int othersSum = 0;
    for (int k = 0; k < IDEOLOGY_COUNT; k++)
        if (k != targetIdeology) othersSum += support[k];

    int remaining = -actualDelta;
    if (othersSum <= 0) return;

    int distributed = 0;
    for (int k = 0; k < IDEOLOGY_COUNT; k++)
    {
        if (k == targetIdeology) continue;
        int share = (remaining * support[k]) / othersSum;
        int v = (int)support[k] + share;
        if (v < 0) v = 0;
        support[k] = (unsigned char)v;
        distributed += share;
    }

    int leftover = remaining - distributed;
    for (int k = 0; k < IDEOLOGY_COUNT && leftover != 0; k++)
    {
        if (k == targetIdeology) continue;
        int v = (int)support[k] + leftover;
        if (v < 0) v = 0;
        support[k] = (unsigned char)v;
        leftover = 0;
    }
}

static void applyDecisionEffects(unsigned short offset, unsigned short length, unsigned char actingCountryId)
{
    if ((int)offset + (int)length > EFFECT_POOL_COUNT) return; // stale-build guard, same as conditions

    for (unsigned short i = 0; i < length; i++)
    {
        const EffectInstr* instr = &effect_pool[offset + i];

        switch (instr->opcode)
        {
            case EFFECTOP_ADD_STABILITY: {
                if (actingCountryId >= COUNTRY_POLITICS_COUNT) break;
                int v = (int)country_politics_runtime[actingCountryId].stability + instr->operand1;
                if (v < 0) v = 0;
                if (v > 100) v = 100;
                country_politics_runtime[actingCountryId].stability = (unsigned char)v;
                break;
            }

            case EFFECTOP_ADD_SUPPORT:
                if (actingCountryId < COUNTRY_POLITICS_COUNT)
                    applySupportDelta(actingCountryId, instr->operand1, instr->operand2);
                break;

            case EFFECTOP_SET_RULING_IDEOLOGY:
                if (actingCountryId < COUNTRY_POLITICS_COUNT)
                    country_politics_runtime[actingCountryId].ruling_ideology = (unsigned char)instr->operand1;
                break;

            case EFFECTOP_SET_PROVINCE_OWNER: {
                int pid = instr->operand1;
                int targetCountry = (instr->operand2 == EFFECT_COUNTRY_SELF) ? actingCountryId : instr->operand2;
                if (pid >= 0 && pid < PROVINCE_OWNER_COUNT)
                    province_owners[pid] = (unsigned char)targetCountry;
                break;
            }

            case EFFECTOP_SET_LEADER: {
                // operand1 is a stable portrait_id, NOT an array index — must search.
                int foundIdx = -1;
                for (int li = 0; li < LEADER_COUNT; li++)
                    if (leaders[li].portrait_id == instr->operand1) { foundIdx = li; break; }
                if (foundIdx >= 0)
                {
                    unsigned char cid  = leaders[foundIdx].country_id;
                    unsigned char ideo = leaders[foundIdx].ideology;
                    if (cid < COUNTRY_POLITICS_COUNT)
                        country_politics_runtime[cid].current_leader[ideo] = (unsigned char)foundIdx;
                }
                break;
            }

            case EFFECTOP_CLEAR_LEADER: {
                unsigned char cid  = (instr->operand1 == EFFECT_COUNTRY_SELF) ? actingCountryId : (unsigned char)instr->operand1;
                unsigned char ideo = (unsigned char)instr->operand2;
                if (cid < COUNTRY_POLITICS_COUNT && ideo < IDEOLOGY_COUNT)
                    country_politics_runtime[cid].current_leader[ideo] = LEADER_NONE;
                break;
            }

            case EFFECTOP_FORM_NATION: {
				unsigned char formedId = (unsigned char)instr->operand1;
				if (formedId >= COUNTRY_COUNT) break;

				transferAllProvinces(actingCountryId, formedId);

				if (formedId != actingCountryId && actingCountryId < COUNTRY_POLITICS_COUNT && formedId < COUNTRY_POLITICS_COUNT)
					country_politics_runtime[formedId] = country_politics_runtime[actingCountryId];

				countryExists[formedId] = true;
				if (formedId != actingCountryId)
				{
					countryExists[actingCountryId] = false;
					swapTurnOrderPositions(actingCountryId, formedId); // formedId now occupies actingCountryId's ROTATION SLOT
				}

				if (actingCountryId == PLAYER_COUNTRY)
					PLAYER_COUNTRY = formedId;

				for (int i = 0; i < FORMABLE_CORE_COUNT; i++)
					if (formable_cores[i].country_id == formedId)
						addRuntimeCore(formable_cores[i].province_id, formedId);

				break;
			}

			case EFFECTOP_ABSORB_COUNTRY: {
				unsigned char absorbedId = (unsigned char)instr->operand1;
				unsigned char intoId = (instr->operand2 == EFFECT_COUNTRY_SELF) ? actingCountryId : (unsigned char)instr->operand2;
				if (absorbedId >= COUNTRY_COUNT || intoId >= COUNTRY_COUNT) break;

				transferAllProvinces(absorbedId, intoId);
				countryExists[absorbedId] = false;
				break;
			}

			case EFFECTOP_ADD_CORE: {
				int pid = instr->operand1;
				unsigned char cid = (instr->operand2 == EFFECT_COUNTRY_SELF) ? actingCountryId : (unsigned char)instr->operand2;
				addRuntimeCore(pid, cid);
				break;
			}
        }
    }
}

void takeDecision(int decisionIdx, unsigned char countryId)
{
    if (!isDecisionAvailable(decisionIdx, countryId)) return; // safety net — UI should already prevent this

    const Decision* d = &decisions[decisionIdx];
    applyDecisionEffects(d->effects_offset, d->effects_length, countryId);

    decision_taken[decisionIdx] = true;
    decisionLastTakenTurn[decisionIdx][countryId] = CURRENT_TURN.current_turn;
}

//---------------------------------------------
// UI — Internal Politics screen
//---------------------------------------------

#define DECISIONS_VISIBLE_ROWS 5
#define DECISION_ROW_H  26
#define DECISION_ROW_Y0 20
#define DECISION_LIST_X 20
#define DECISION_LIST_W 216

#define SCROLLBAR_X     240
#define SCROLLBAR_W     10
#define SCROLLBAR_Y0    DECISION_ROW_Y0
#define SCROLLBAR_H     (DECISIONS_VISIBLE_ROWS * DECISION_ROW_H)

#define RETURN_BTN_X 4
#define RETURN_BTN_Y 160
#define RETURN_BTN_S 24

static int visibleDecisionIndices[DECISION_COUNT];
static int decisionListCount   = 0;
static int decisionListScroll  = 0;
static int selectedDecisionIdx = -1;
static bool decisionsDirty     = true;

static int drawMultilineText(TextEngine engine, int x, int startY, const char* text, int lineHeight)
{
    char lineBuf[64];
    int y = startY;
    const char* p = text;

    while (*p)
    {
        int i = 0;
        while (*p && *p != '\n' && i < (int)sizeof(lineBuf) - 1)
            lineBuf[i++] = *p++;
        lineBuf[i] = '\0';
        if (*p == '\n') p++;

        drawText(engine, x, y, lineBuf);
        y += lineHeight;
    }
    return y;
}

static void rebuildVisibleDecisionList()
{
    decisionListCount = 0;
    for (int i = 0; i < DECISION_COUNT; i++)
        if (isDecisionVisible(i, PLAYER_COUNTRY))
            visibleDecisionIndices[decisionListCount++] = i;

    int maxScroll = decisionListCount - DECISIONS_VISIBLE_ROWS;
    if (maxScroll < 0) maxScroll = 0;
    if (decisionListScroll > maxScroll) decisionListScroll = maxScroll;
}

static void updateDecisionDetailDisplay()
{
    clearText(TEXT_ENGINE_SUB);
    if (selectedDecisionIdx >= 0)
    {
        const Decision* d = &decisions[selectedDecisionIdx];
        int y = 8;

        drawText(TEXT_ENGINE_SUB, 8, y, d->title);
        y += 14;

        y = drawMultilineText(TEXT_ENGINE_SUB, 8, y, d->flavor_text, 10);
        y += 4;

        drawText(TEXT_ENGINE_SUB, 8, y, "EFFECT:");
        y += 10;
        y = drawMultilineText(TEXT_ENGINE_SUB, 8, y, d->effect_text, 10);
        y += 4;

        drawText(TEXT_ENGINE_SUB, 8, y, "REQUIRES:");
        y += 10;
        drawMultilineText(TEXT_ENGINE_SUB, 8, y, d->prerequisites_text, 10);
    }
    commitText(TEXT_ENGINE_SUB);
}

static void scrollbarThumbGeometry(int* outThumbH, int* outTravel)
{
    int thumbH = (SCROLLBAR_H * DECISIONS_VISIBLE_ROWS) / decisionListCount;
    if (thumbH < 8) thumbH = 8;
    if (thumbH > SCROLLBAR_H) thumbH = SCROLLBAR_H;
    *outThumbH = thumbH;
    *outTravel = SCROLLBAR_H - thumbH;
}

static void drawScrollbar()
{
    if (decisionListCount <= DECISIONS_VISIBLE_ROWS)
        return;

    u16* vram = (u16*)BG_BMP_RAM(0);
    u16 track = BGR15(6, 6, 8);
    u16 thumb = BGR15(16, 18, 24);

    for (int py = SCROLLBAR_Y0; py < SCROLLBAR_Y0 + SCROLLBAR_H; py++)
        for (int px = SCROLLBAR_X; px < SCROLLBAR_X + SCROLLBAR_W; px++)
            vram[py * SCREEN_W + px] = track;

    int thumbH, travel;
    scrollbarThumbGeometry(&thumbH, &travel);
    int maxScroll = decisionListCount - DECISIONS_VISIBLE_ROWS;
    int thumbY = SCROLLBAR_Y0 + (maxScroll > 0 ? (travel * decisionListScroll) / maxScroll : 0);

    for (int py = thumbY; py < thumbY + thumbH && py < SCROLLBAR_Y0 + SCROLLBAR_H; py++)
        for (int px = SCROLLBAR_X; px < SCROLLBAR_X + SCROLLBAR_W; px++)
            vram[py * SCREEN_W + px] = thumb;
}

static void handleDecisionsDrag(int keys)
{
    if (!(keys & KEY_TOUCH)) return;
    if (decisionListCount <= DECISIONS_VISIBLE_ROWS) return;

    touchPosition touch;
    touchRead(&touch);
    if (touch.px < SCROLLBAR_X || touch.px >= SCROLLBAR_X + SCROLLBAR_W) return;
    if (touch.py < SCROLLBAR_Y0 || touch.py >= SCROLLBAR_Y0 + SCROLLBAR_H) return;

    int thumbH, travel;
    scrollbarThumbGeometry(&thumbH, &travel);
    int maxScroll = decisionListCount - DECISIONS_VISIBLE_ROWS;

    int rel = touch.py - SCROLLBAR_Y0 - thumbH / 2;
    if (rel < 0) rel = 0;
    if (rel > travel) rel = travel;

    int newScroll = (travel > 0) ? (rel * maxScroll + travel / 2) / travel : 0;
    if (newScroll < 0) newScroll = 0;
    if (newScroll > maxScroll) newScroll = maxScroll;

    if (newScroll != decisionListScroll)
    {
        decisionListScroll = newScroll;
        decisionsDirty = true;
    }
}

static void drawDecisionsScreen()
{
    renderMenuBackground();

    clearText(TEXT_ENGINE_MAIN);
    drawText(TEXT_ENGINE_MAIN, 60, 6, "INTERNAL POLITICS");

    int y = DECISION_ROW_Y0;
    int shown = 0;
    for (int i = decisionListScroll; i < decisionListCount && shown < DECISIONS_VISIBLE_ROWS; i++, shown++)
    {
        int decisionIdx = visibleDecisionIndices[i];
        const Decision* d = &decisions[decisionIdx];
        bool available = isDecisionAvailable(decisionIdx, PLAYER_COUNTRY);
        bool selected  = (decisionIdx == selectedDecisionIdx);

        drawButtonRect(DECISION_LIST_X, y, DECISION_LIST_W, DECISION_ROW_H - 4, selected, available);
        drawText(TEXT_ENGINE_MAIN, DECISION_LIST_X + 8, y + 8, d->title);
        y += DECISION_ROW_H;
    }

    drawScrollbar();

    bool canTake = (selectedDecisionIdx >= 0) && isDecisionAvailable(selectedDecisionIdx, PLAYER_COUNTRY);
    drawButtonRect(70, 160, 116, 26, false, canTake);
    drawText(TEXT_ENGINE_MAIN, 90, 168, canTake ? "TAKE DECISION" : "LOCKED");

    drawButtonRect(RETURN_BTN_X, RETURN_BTN_Y, RETURN_BTN_S, RETURN_BTN_S, false, true);
    drawText(TEXT_ENGINE_MAIN, RETURN_BTN_X + 8, RETURN_BTN_Y + 8, "<");

    commitText(TEXT_ENGINE_MAIN);
}

static void returnFromDecisions()
{
    currentState = STATE_GAME;
    needsRedraw  = true; // BG0 was covering the map — force a clean re-blit
    videoSetMode(MODE_5_2D | DISPLAY_BG3_ACTIVE | DISPLAY_SPR_ACTIVE | DISPLAY_SPR_1D);
    clearText(TEXT_ENGINE_MAIN);
    commitText(TEXT_ENGINE_MAIN);
}

static void handleDecisionsTap(int px, int py)
{
    if (px >= RETURN_BTN_X && px < RETURN_BTN_X + RETURN_BTN_S &&
        py >= RETURN_BTN_Y && py < RETURN_BTN_Y + RETURN_BTN_S)
    {
        returnFromDecisions();
        return;
    }

    int y = DECISION_ROW_Y0;
    int shown = 0;
    for (int i = decisionListScroll; i < decisionListCount && shown < DECISIONS_VISIBLE_ROWS; i++, shown++)
    {
        if (px >= DECISION_LIST_X && px < DECISION_LIST_X + DECISION_LIST_W &&
            py >= y && py < y + DECISION_ROW_H - 4)
        {
            selectedDecisionIdx = visibleDecisionIndices[i];
            updateDecisionDetailDisplay();
            decisionsDirty = true;
            return;
        }
        y += DECISION_ROW_H;
    }

    if (px >= 70 && px < 186 && py >= 160 && py < 186 &&
        selectedDecisionIdx >= 0 && isDecisionAvailable(selectedDecisionIdx, PLAYER_COUNTRY))
    {
        takeDecision(selectedDecisionIdx, PLAYER_COUNTRY);
        rebuildVisibleDecisionList();
        updateDecisionDetailDisplay();
        decisionsDirty = true;
    }
}

void enterDecisionsState()
{
    currentState        = STATE_DECISIONS;
    selectedDecisionIdx = -1;
    decisionListScroll  = 0;
    rebuildVisibleDecisionList();
    decisionsDirty = true;
	hideFlag();

    videoSetMode(MODE_5_2D | DISPLAY_BG0_ACTIVE | DISPLAY_BG3_ACTIVE | DISPLAY_SPR_ACTIVE);
    clearText(TEXT_ENGINE_SUB);
    commitText(TEXT_ENGINE_SUB);
}

void updateDecisionsState(int keys, int pressed)
{
    if (pressed & KEY_B)
    {
        returnFromDecisions();
        return;
    }

    if (pressed & KEY_UP)
    {
        if (decisionListScroll > 0) { decisionListScroll--; decisionsDirty = true; }
    }
    if (pressed & KEY_DOWN)
    {
        int maxScroll = decisionListCount - DECISIONS_VISIBLE_ROWS;
        if (maxScroll < 0) maxScroll = 0;
        if (decisionListScroll < maxScroll) { decisionListScroll++; decisionsDirty = true; }
    }

    handleDecisionsDrag(keys);

    if (pressed & KEY_TOUCH)
    {
        touchPosition touch;
        touchRead(&touch);
        handleDecisionsTap(touch.px, touch.py);
    }

    if (decisionsDirty)
    {
        drawDecisionsScreen();
        decisionsDirty = false;
    }
}