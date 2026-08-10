#ifndef DECISIONS_DATA_H
#define DECISIONS_DATA_H

// Keep in sync with CONDOP_ORDER in decision_editor.py
typedef enum {
    CONDOP_AND = 0,
    CONDOP_OR = 1,
    CONDOP_NOT = 2,
    CONDOP_COUNTRY_IS = 3,
    CONDOP_STABILITY_GE = 4,
    CONDOP_STABILITY_LE = 5,
    CONDOP_SUPPORT_GE = 6,
    CONDOP_SUPPORT_LE = 7,
    CONDOP_RULING_IS = 8,
    CONDOP_CONTROLS_PROVINCE = 9,
    CONDOP_DECISION_TAKEN = 10,
} ConditionOp;

// Postfix (RPN) instruction. AND/OR: pop 2 push 1 ; NOT: pop 1 push 1 ;
// all others: push 1, a leaf evaluated against the country being checked.
//   COUNTRY_IS: op1=country_id
//   STABILITY_GE/LE: op1=value(0-100)
//   SUPPORT_GE/LE: op1=ideology, op2=value(0-100)
//   RULING_IS: op1=ideology
//   CONTROLS_PROVINCE: op1=province_id
//   DECISION_TAKEN: op1=decision index into decisions[] — requires a runtime
//     `bool decision_taken[DECISION_COUNT]` global (any country, ever), not built yet
typedef struct { unsigned char opcode; short operand1; short operand2; } ConditionInstr;

#define CONDITION_ALWAYS_TRUE 0xFFFF // sentinel length: no tree, always true

// Keep in sync with EFFECTOP_ORDER in decision_editor.py
typedef enum {
    EFFECTOP_ADD_STABILITY = 0,
    EFFECTOP_ADD_SUPPORT = 1,
    EFFECTOP_SET_RULING_IDEOLOGY = 2,
    EFFECTOP_SET_PROVINCE_OWNER = 3,
    EFFECTOP_SET_LEADER = 4,
    EFFECTOP_CLEAR_LEADER = 5,
    EFFECTOP_FORM_NATION = 6,
} EffectOp;

#define EFFECT_COUNTRY_SELF -1 // sentinel: acting country

//   ADD_STABILITY: op1=delta (signed, acting country)
//   ADD_SUPPORT: op1=ideology, op2=delta (signed, acting country)
//   SET_RULING_IDEOLOGY: op1=ideology (acting country)
//   SET_PROVINCE_OWNER: op1=province_id, op2=country_id or EFFECT_COUNTRY_SELF
//   SET_LEADER: op1=leader PORTRAIT_ID (stable id, NOT array index) — game code
//     must linear-search leaders[] for a matching portrait_id at apply-time to find
//     that leader's country_id/ideology/current array index
//   CLEAR_LEADER: op1=country_id or EFFECT_COUNTRY_SELF, op2=ideology
//   FORM_NATION: op1=target_country_id — STUB, mechanics not yet designed
typedef struct { unsigned char opcode; short operand1; short operand2; } EffectInstr;

typedef struct {
    const char* title;
    const char* flavor_text;         // may contain literal \n — split before rendering
    const char* effect_text;          // human-authored, not auto-generated
    const char* prerequisites_text;   // auto-generated from availability, editable — SHOW to player
    short cooldown_turns;              // DECISION_ONCE_ONLY(-1) = never repeatable; else turns before retakeable
    unsigned short visibility_offset;
    unsigned short visibility_length;   // CONDITION_ALWAYS_TRUE = always visible
    unsigned short availability_offset;
    unsigned short availability_length; // CONDITION_ALWAYS_TRUE = always available
    unsigned short effects_offset;
    unsigned short effects_length;
} Decision;

#define DECISION_ONCE_ONLY -1

#define CONDITION_POOL_COUNT 28
extern const ConditionInstr condition_pool[CONDITION_POOL_COUNT];

#define EFFECT_POOL_COUNT 27
extern const EffectInstr effect_pool[EFFECT_POOL_COUNT];

#define DECISION_COUNT 6
extern const Decision decisions[DECISION_COUNT];

#endif
