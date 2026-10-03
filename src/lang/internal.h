/* Internal data structures shared by the compiler stages:
 * lex.c -> parse.c -> check.c -> gen.c, driven by compile.c. */
#ifndef MEI_LANG_INTERNAL_H
#define MEI_LANG_INTERNAL_H

#include "lang.h"
#include <stdint.h>
#include <stddef.h>
#include <stdarg.h>

/* ---------------------------------------------------------------- util.c */

typedef struct { const char *file; int line, col; } Loc;

void *ar_alloc(size_t n);                 /* zeroed; freed by ar_free_all */
char *ar_strdup(const char *s);
char *ar_strndup(const char *s, size_t n);
char *ar_printf(const char *fmt, ...);
void ar_free_all(void);

typedef struct { char *p; size_t len, cap; } Buf;
void buf_putc(Buf *b, char c);
void buf_puts(Buf *b, const char *s);
void buf_putn(Buf *b, const char *s, size_t n);
void buf_printf(Buf *b, const char *fmt, ...);
void buf_vprintf(Buf *b, const char *fmt, va_list ap);
void buf_free(Buf *b);

/* Source files, kept so errors can quote the offending line. */
typedef struct SrcFile { const char *path; const char *text; size_t len; struct SrcFile *next; } SrcFile;
SrcFile *src_register(const char *path, const char *text, size_t len);

/* Errors: the first error aborts compilation (longjmp back to meic_compile). */
_Noreturn void error_at(Loc loc, const char *fmt, ...);
_Noreturn void error_plain(const char *fmt, ...);
void error_reset(char *buf, size_t len);
void warn_at(Loc loc, const char *fmt, ...);   /* a warning (compilation goes on) */
void warn_reset(void);
char *warn_take(void);                          /* malloc'd text of the warnings, or NULL */
extern void *g_error_jmp;   /* jmp_buf * */

/* ---------------------------------------------------------------- lex.c */

typedef enum { TK_EOF, TK_NL, TK_IDENT, TK_INT, TK_FIXED, TK_STR, TK_OP } TokKind;

typedef struct {
    TokKind k;
    Loc loc;
    const char *s;     /* identifier / operator text / string contents (unescaped) */
    size_t slen;       /* string length (may contain NULs) */
    int64_t ival;      /* TK_INT value; TK_FIXED raw 16.16 value */
} Token;

typedef struct {
    const char *src, *p, *end;
    const char *file;
    int line;
    const char *line_start;
    char nest[256];    /* open brackets: '(' for ( and [ (newlines not significant), '{' for { */
    int depth;
    Token last;        /* previous significant token, for newline insertion */
} Lexer;

void lex_init(Lexer *L, const char *file, const char *src, size_t len);
Token lex_next(Lexer *L);
/* After a `{` token: returns the raw text up to the matching `}` (consumed). */
char *lex_raw_block(Lexer *L, Loc *start);

/* ---------------------------------------------------------------- types */

typedef enum {
    TY_VOID, TY_BOOL, TY_S8, TY_S16, TY_S32, TY_U8, TY_U16, TY_U32, TY_FIXED,
    TY_VEC2, TY_VEC3, TY_VEC4, TY_IVEC4, TY_MAT4,
    TY_PTR, TY_ARRAY, TY_STRUCT,
    TY_UINT,      /* untyped integer constant */
    TY_UFIXED,    /* untyped fixed constant */
    TY_NULL,      /* type of `null` */
    TY_FUNC,      /* function value: 16 bytes, [code address, 3 captured words]; elem = result,
                     params = parameter types. Held in vector registers like a vec4. */
    TY_ENUM,      /* enumeration: elem = underlying integer type */
} TyKind;

typedef struct Type Type;
typedef struct Field {
    const char *name; Type *type; int offset; Loc loc;
    struct Expr *def;      /* default value for struct literals that omit the field, or NULL */
    int def_checked;
} Field;

struct Type {
    TyKind k;
    const char *name;      /* builtin or struct name */
    Type *elem;            /* pointer / array element */
    int64_t n;             /* array length */
    Field *fields; int nfields;
    int size, align;
    int layout;            /* struct: 0 not laid out, 1 in progress, 2 done */
    Loc loc;
    struct StructDecl *decl;
    Type *ptr_cache;       /* interned *T */
    Type *arr_list;        /* interned arrays of this element type */
    Type *arr_sib;         /* next array type in the element's arr_list */
    Type **params; int nparams;  /* TY_FUNC parameter types */
    Type *func_next;       /* interned function types (global list) */
    struct EnumDecl *edecl;      /* TY_ENUM */
    const char **vnames; int64_t *vvals; int nvariants;   /* TY_ENUM, after resolution */
};

extern Type *ty_void, *ty_bool, *ty_s8, *ty_s16, *ty_s32, *ty_u8, *ty_u16, *ty_u32, *ty_fixed,
            *ty_vec2, *ty_vec3, *ty_vec4, *ty_ivec4, *ty_mat4, *ty_uint, *ty_ufixed, *ty_null;

void types_init(void);
Type *ty_ptr(Type *t);
Type *ty_array(Type *t, int64_t n);
const char *ty_str(Type *t);
int ty_is_int(Type *t);       /* s8..u32 (not untyped) */
int ty_is_signed(Type *t);
int ty_is_scalar(Type *t);    /* lives in one scalar register: ints, fixed, bool, pointers */
int ty_is_vec(Type *t);       /* vec2..ivec4 */
int ty_is_aggr(Type *t);      /* struct, array, mat4: lives in memory */
int ty_lanes(Type *t);        /* vec2: 2, vec3: 3, vec4/ivec4: 4 */
Type *ty_base(Type *t);       /* an enum's underlying integer type; other types unchanged */
Type *ty_func(Type **params, int n, Type *ret);

/* ---------------------------------------------------------------- AST */

typedef enum {
    B_ADD, B_SUB, B_MUL, B_DIV, B_MOD, B_AND, B_OR, B_XOR, B_SHL, B_SHR,
    B_EQ, B_NE, B_LT, B_LE, B_GT, B_GE, B_LAND, B_LOR,
    U_NEG, U_NOT, U_BNOT, U_ADDR, U_DEREF,
} OpKind;

typedef struct TypeExpr {
    int k;                 /* 0 name, 1 pointer, 2 array, 3 function */
    Loc loc;
    const char *name;
    struct TypeExpr *elem;   /* pointer/array element; function result (NULL: none) */
    struct TypeExpr **params; int nparams;
    struct Expr *len;
    Type *resolved;
} TypeExpr;

typedef enum {
    E_INT, E_FIXED, E_BOOL, E_STR, E_NULL, E_NAME, E_UNARY, E_BINARY, E_CALL,
    E_INDEX, E_FIELD, E_CAST, E_ARRAY, E_STRUCT, E_SIZEOF, E_CONV,
    E_FUNC,       /* function literal */
    E_MATCH,      /* match expression: a = scrutinee, arms[i].value the arm values */
} ExprKind;

/* Builtins implemented inline by the code generator. */
typedef enum {
    BI_NONE, BI_VEC2, BI_VEC3, BI_VEC4, BI_IVEC4, BI_DOT, BI_CROSS, BI_LEN,
    BI_BITS, BI_FROM_BITS, BI_ABS, BI_MIN, BI_MAX, BI_CLAMP, BI_LERP, BI_LENGTH, BI_NORMALIZE,
    BI_NCLIP, BI_OTZ, BI_CLERP,     /* the geometry instructions of the same names */
    BI_KIND, BI_RAW,                /* assert_eq() reports: a value's print kind, its raw 32 bits */
    BI_MAP, BI_MAP_INTO, BI_FILTER, BI_FILTER_INTO, BI_REDUCE, BI_EACH,
} Builtin;

typedef struct Sym Sym;
typedef struct Local Local;
struct MatchArm;

typedef struct Expr {
    ExprKind k;
    Loc loc;
    OpKind op;
    struct Expr *a, *b;
    struct Expr **args; int nargs;
    const char **fnames;   /* struct literal field names (parallel to args) */
    const char *name;      /* E_NAME, E_FIELD, E_STRUCT type name */
    TypeExpr *texpr;       /* E_CAST, E_SIZEOF */
    const char *str; size_t slen;  /* E_STR */
    int64_t ival;          /* literal value (E_FIXED: raw 16.16) */
    /* set by the checker */
    Type *ty;
    int isconst;           /* scalar: cval; vector: cvec */
    int64_t cval;
    int32_t cvec[4];
    Sym *sym;
    Builtin bi;
    Field *field;
    int lanes[4], nlanes;  /* E_FIELD on a vector: swizzle lanes */
    struct Func *callee;   /* E_CALL of a function */
    Type *conv_from;       /* E_CONV: source type (a->ty), ty is destination */
    int indirect;          /* E_CALL through a function value (e->a) */
    struct Func *lambda;   /* E_FUNC: the function it defines */
    Local *hid[8];         /* intrinsic loops: hidden loop-state locals (5-7: captures of a known literal) */
    int elem_byref;        /* each(): the function takes a pointer to the element */
    struct Func *target;   /* intrinsics: the function applied, when known statically */
    int has_count;         /* intrinsics: an explicit element count was given */
    struct MatchArm *arms; int narms;   /* E_MATCH */
    Sym *chk;              /* meic -g: the message of this expression's run-time check (a string) */
} Expr;

typedef enum {
    S_BLOCK, S_EXPR, S_VAR, S_ASSIGN, S_IF, S_WHILE, S_FOR, S_BREAK, S_CONTINUE, S_RETURN, S_ASM,
    S_MATCH, S_CONST,
} StmtKind;

typedef struct MatchArm {
    Loc loc;
    struct Expr **pats; int npats;   /* constant patterns; none for the else arm */
    int is_else;
    struct Stmt *body;     /* match statement */
    struct Expr *value;    /* match expression */
} MatchArm;

typedef struct AsmRef { const char *text; Loc loc; } AsmRef;

typedef struct Stmt {
    StmtKind k;
    Loc loc;
    struct Stmt **list; int n;     /* S_BLOCK */
    Expr *e, *e2;                  /* expr / lhs,rhs / cond / range lo,hi / return value */
    int op;                        /* S_ASSIGN: -1 plain, else OpKind */
    struct Stmt *then, *els;       /* if / loop body */
    Local *var;                    /* S_VAR, S_FOR */
    const char *name; TypeExpr *texpr; int is_let;
    const char *asm_text; Loc asm_loc;
    Local *for_end;                /* S_FOR: hidden end-bound local */
    MatchArm *arms; int narms;     /* S_MATCH (var: hidden scrutinee local) */
    int pos, pos2;                 /* codegen: live-range positions (loops: header, bottom) */
    Local **ips; Expr **ipinit; int *ipstep; int nips;   /* S_FOR: induction pointers (&a[i]) */
    int end_direct;                /* S_FOR: the end bound is a local the loop never changes: compare with it */
} Stmt;

struct Local {
    const char *name;
    Type *ty;
    Loc loc;
    int immutable;
    int is_param;
    int is_loopvar;
    int has_range;        /* a loop variable with constant bounds: its value is in [rlo, rhi) */
    int64_t rlo, rhi;
    int is_capture;       /* a function literal's copy of a captured local (arrives in r6-r8) */
    int points_local;     /* pointer seen holding the address of local storage (dangling check) */
    int addr_taken;
    int in_asm;           /* named in an inline asm block: must live in a register */
    Sym *csym;            /* a local `const`: its constant (the Local only names it in a scope) */
    int64_t weight;       /* use count weighted by loop depth */
    /* codegen */
    int home;             /* 0 memory, 1 scalar register, 2 vector register */
    int reg;
    int off;              /* stack offset (memory home) */
    int in_reg_arg;       /* param: arrives in register (r1-r4 / v0-v3) */
    int arg_reg;
    int stack_arg_off;    /* param: offset in the caller's outgoing area (if not in a register) */
    int start, end;       /* live range in statement positions */
    int crosses_call;     /* a call (or asm block) happens inside the live range */
    uint32_t clob;        /* registers those calls may change (as Func.clob) */
    int crosses_xfm;      /* a mat4 * vector (which loads v4-v7) happens inside the live range */
    int dead;             /* never read or written (a constant loop bound's end local): no home */
    int elided;           /* a `let` whose value was substituted into its uses: no home */
    int captured;         /* a function literal captures it */
    int nreads, nwrites;  /* uses as a value / plain assignments to it (meic -W) */
};

typedef struct Param { const char *name; TypeExpr *texpr; Type *ty; Loc loc; Local *local; } Param;

typedef struct Func {
    const char *name;
    const char *label;
    Loc loc;
    Param *params; int nparams;
    TypeExpr *ret_texpr;
    Type *ret;
    Stmt *body;
    int is_asm;
    const char *asm_text; Loc asm_loc;
    Sym *sym;
    Local **locals; int nlocals, caplocals;
    int has_call, has_asm, uses_xfm, uses_io;
    int max_out;          /* outgoing stack-argument area */
    struct Func **calls; int ncalls, capcalls;   /* referenced functions */
    Sym **refs; int nrefs, caprefs;              /* referenced data symbols */
    int reachable;
    int is_init;          /* synthesized global-initialiser function */
    Local *hidden_ret;    /* aggregate return: destination pointer */
    Local *iobase;        /* hidden local holding 0xFF0000 */
    int checked;          /* body already checked (function literals) */
    int is_lambda;
    Expr *lambda_body;    /* `fn(x) => expr` form */
    Local **caps;         /* captured copies (locals of this literal), in capture-word order */
    Local **cap_outer;    /* the captured locals of the enclosing function */
    Loc *cap_locs;        /* first use of each capture */
    int ncaps, capcaps;
    int noescape;         /* literal passed straight to map/filter/... or called at once */
    Sym *stack_msg;       /* meic -g: the message of the stack check at entry */
    int inl;              /* inliner: 0 not decided, 1 inlinable (`return E` of a small pure E), 2 not */
    Expr *inl_e;          /* the E of an inlinable function */
    uint32_t clob;        /* codegen: registers a call to it may change (bits 1-8 r1-r8, 16-23 v0-v7) */
    int clob_known;       /* clob is set (the function was generated before its callers) */
    int weak;             /* `weak fn`: a default that another definition of the name replaces */
    struct Func *overrides;   /* the weak function this one replaced (signatures must match) */
} Func;

typedef enum { SY_TYPE, SY_CONST, SY_DATA, SY_GLOBAL, SY_REG, SY_EMBED, SY_FUNC, SY_LOCAL, SY_BUILTIN } SymKind;

struct Sym {
    SymKind k;
    const char *name;
    Loc loc;
    Type *ty;
    TypeExpr *texpr;
    Expr *init;
    int state;             /* lazy resolution: 0 todo, 1 in progress, 2 done */
    int64_t cval;          /* SY_CONST scalar */
    int32_t cvec[4];       /* SY_CONST vector */
    uint32_t addr;         /* SY_GLOBAL: RAM address; SY_REG: I/O address */
    const char *label;
    Func *fn;
    Local *local;
    Builtin bi;
    /* SY_EMBED */
    const char *path; Expr *off_e, *len_e;
    const uint8_t *data; size_t datalen;
    int reachable;
    int is_str;            /* SY_DATA string literal */
    const char *str; size_t slen;
    int user;              /* declared by the cart (not the standard library) */
    int module;            /* isolated source module number, or 0 for legacy global names */
    int priv;              /* `private`: visible in its file only; the file's number (from 1) */
    struct Func **dfuncs; int ndfuncs, capdfuncs;   /* SY_DATA: functions named in the data */
};

typedef struct EnumDecl {
    const char *name; Loc loc; TypeExpr *base;
    const char **names; struct Expr **vals; Loc *locs; int n;
    Type *ty; int state;
} EnumDecl;

typedef struct StructDecl { const char *name; Loc loc; const char **fnames; TypeExpr **ftypes; Loc *flocs; int nf; Type *ty;
                            struct Expr **fdefs; /* field defaults (NULL entries: none) */ } StructDecl;

typedef struct Program {
    Func **funcs; int nfuncs, capfuncs;
    Sym **globals; int nglobals, capglobals;   /* SY_GLOBAL in declaration order */
    Sym **datas; int ndatas, capdatas;         /* SY_DATA + SY_EMBED + strings */
    StructDecl **structs; int nstructs, capstructs;
    EnumDecl **enums; int nenums, capenums;
    Sym **consts; int nconsts, capconsts;
    Sym **regs; int nregs, capregs;
    const char *title;
    const char *cart_id;   /* `cart "Title", "ID"`: header bytes 40-55 (NULL: none) */
    int debug;             /* MEI_CHECK_* bits (meic -g) */
    int wextra;            /* meic -W */
    Func *init_fn;         /* synthesized global initialisers */
    uint32_t ram_end;
} Program;

/* ---------------------------------------------------------------- parse.c */

typedef struct Compiler Compiler;
/* Parses one file into the program; imports are resolved through compiler_import. */
void parse_file(Compiler *C, Program *P, const char *path, const char *text, size_t len);

/* ---------------------------------------------------------------- compile.c */

struct Compiler {
    const MeiCompileOptions *opt;
    char **seen; int nseen, capseen;      /* imported files (canonical paths) */
    Program *prog;
    int importing_stdlib;
    const char *stdlib_dir;               /* where the prelude was found (NULL: no stdlib) */
};
/* Imports `path` (relative to `from_file`); each file is parsed once. */
void compiler_import(Compiler *C, const char *from_file, const char *path, Loc loc);
void compiler_import_as(Compiler *C, const char *from_file, const char *path, const char *alias, Loc loc);
/* Loads a binary file relative to from_file (for embed). */
const uint8_t *compiler_load_binary(Compiler *C, const char *from_file, const char *path, Loc loc, size_t *len);

/* ---------------------------------------------------------------- symbols */

Sym *sym_lookup_global(const char *name);              /* as seen from cart code */
Sym *sym_lookup(const char *name, const char *from_file);
Sym *sym_lookup_layer(const char *name, int layer);   /* 0: built-ins + stdlib, 1: cart */
Sym *sym_lookup_private(const char *name, const char *file);   /* `private` in that file */
Sym *sym_private_elsewhere(const char *name, const char *from_file);
_Noreturn void error_unknown(Loc loc, const char *what, const char *name);
void sym_define_global(Sym *s);
void sym_define_private(Sym *s, const char *file);    /* sets s->priv */
void mark_stdlib_file(const char *path);
int file_is_stdlib(const char *path);
void symtab_reset(void);
void module_begin(const char *file, int isolated);
int file_is_module(const char *file);
Sym *sym_lookup_module(const char *name, const char *file, int public_only);
void sym_define_module(Sym *s, const char *file);
void module_import(const char *from, const char *target, const char *alias, Loc loc);
int module_has_alias(const char *file, const char *name);
Sym *sym_lookup_qualified(const char *name, const char *file);
void module_publish(const char *file, Program *P);

/* ---------------------------------------------------------------- check.c */

void check_program(Program *P);
int fits_s18(int64_t v);
/* For a link-time address constant in const data (an embed, a string or other const data, a
   function, or one of these converted to a pointer / u32 / s32): its label; else NULL. */
const char *const_addr_label(Expr *e);

/* ---------------------------------------------------------------- gen.c */

/* Generates assembly for the whole program. */
void gen_program(Program *P, Buf *out);

#define RAM_GLOBALS_BASE 0x000100u
#define IO_BASE_ADDR     0xFF0000u

#endif
