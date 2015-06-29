import pyd.pyd;

import std.typetuple : Arguments = TypeTuple, Map = staticMap, Filter;
import std.typecons : tuple, Tuple;
import std.traits;

struct pdef(Args ...){}

/*
 * With the builtin alias declaration, you cannot declare
 * aliases of, for example, literal values. You can alias anything
 * including literal values via this template.
 */
// symbols and literal values
template Alias(alias a)
{
    static if (__traits(compiles, { alias x = a; }))
        alias Alias = a;
    else static if (__traits(compiles, { enum x = a; }))
        enum Alias = a;
    else
        static assert(0, "Cannot alias " ~ a.stringof);
}
// types and tuples
template Alias(a...)
{
    alias Alias = a;
}

unittest
{
    enum abc = 1;
    static assert(__traits(compiles, { alias a = Alias!(123); }));
    static assert(__traits(compiles, { alias a = Alias!(abc); }));
    static assert(__traits(compiles, { alias a = Alias!(int); }));
    static assert(__traits(compiles, { alias a = Alias!(1,abc,int); }));
}

bool containsPdef(attrs...)()
{
    foreach(attr; attrs)
        static if(is(attr == pdef!Args, Args...))
        {
            return true;
            break;
        }
    return false;
}

private auto registerFunctionImpl(alias define, alias parent, string mem)()
{
    //pragma(msg, "callable");
    alias ols = Arguments!(__traits(getOverloads, parent, mem));
    foreach(i, ol; ols)
    {
        alias attrs = Arguments!(__traits(getAttributes, ol));
        static if(containsPdef!attrs)
            foreach(attr; attrs)
            {
                static if(is(attr == pdef!Args, Args...))
                {
                    return define!(ol, Args)();
                    break;
                }
            }
        // issue 14747
        else static if(i == ols.length - 1)
        {
            return;
            break;
        }
    }
    // issue 14747
    assert(0);
}

alias registerFunction(alias parent, string mem) = registerFunctionImpl!(def, parent, mem);

alias MemberFunction(alias parent, string mem) = ReturnType!(registerFunctionImpl!(Def, parent, mem));
alias StaticMemberFunction(alias parent, string mem) = ReturnType!(registerFunctionImpl!(StaticDef, parent, mem));
alias PropertyMember(alias parent, string mem) = ReturnType!(registerFunctionImpl!(Property, parent, mem));

private auto MemberHelper(alias parent, string mem)()
{
    alias agg = Alias!(mixin(`parent.`~mem));

    alias attrs = Arguments!(__traits(getAttributes, agg));
    foreach(i, attr; attrs)
    {
        static if(is(attr == pdef!Args, Args...))
        {
            return Member!(mem, Args)();
            break;
        }
        // issue 14747
        else static if(i == attrs.length - 1)
            return;
    }
    // issue 14747
    assert(0);
}

alias _Member(alias parent, string mem) = ReturnType!(MemberHelper!(parent, mem));

auto registerAggregateType(string aggStr, alias parent)()
{
    alias agg = Alias!(mixin(`parent.`~aggStr));

    alias attrs = Arguments!(__traits(getAttributes, agg));
    foreach(attr; attrs)
    {
        static if(is(attr == pdef!Args, Args...))
        {
            return wrap_class!(agg, Args, Map!(Symbol!agg, __traits(allMembers, agg)))();
            /+
            import std.algorithm, std.string;
            /*pragma(msg, `return wrap_class!(agg, Args, ` ~
                        [__traits(allMembers, agg)]
                            .map!(a => `registerSymbol!("` ~ a ~ `", agg)()`).join(", ") ~ `);`);*/
            mixin(`return wrap_class!(agg, Args, ` ~
                        [__traits(allMembers, agg)]
                            .map!(a => `registerSymbol!("` ~ a ~ `", agg)`).join(", ") ~ `);`);+/
        }
    }
}

template Symbol(alias parent)
{
    alias Symbol(string mem) = .Symbol!(mem, parent);
}

template Symbol(string mem, alias parent)
{
    pragma(msg, "registering " ~ parent.stringof ~ '.' ~ mem);
    static if(is(parent == struct) || is(parent == class))
    {
        pragma(msg, "with class/struct parent");
        static if(!(__traits(compiles, mixin(`isAggregateType!(parent.`~mem~')'))
                    && mixin(`isAggregateType!(parent.`~mem~')')
                   )
                    && mixin(`isCallable!(parent.`~mem~')'))
        {
            static if(__traits(isStaticFunction, mixin(`parent.`~mem)))
            {
                pragma(msg, "as static member function");
                alias Symbol =  StaticMemberFunction!(parent, mem);
            }
            static if(functionAttributes!(mixin(`parent.`~mem)) & FunctionAttribute.property)
            {
                pragma(msg, "as property member");
                alias Symbol = PropertyMember!(parent, mem);
            }
            else
            {
                pragma(msg, "as member function");
                alias Symbol =  MemberFunction!(parent, mem);
            }
        }
        else
        {
            pragma(msg, "as member");
            alias Symbol = _Member!(parent, mem);
        }
    }
    else static assert(false);
}

void registerModuleScopeSymbol(string mem, alias parent)()
{
    pragma(msg, "registering " ~ parent.stringof ~ '.' ~ mem);
    static if(mixin(`isCallable!(parent.`~mem~')'))
    {
        pragma(msg, "as free function");
        registerFunction!(parent, mem);
    }
    else static if(__traits(compiles, mixin(`isAggregateType!(parent.`~mem~')'))
            && mixin(`isAggregateType!(parent.`~mem~')'))
    {
        pragma(msg, "as aggregate type");
        registerAggregateType!(mem, parent);
    }
    else pragma(msg, "not registered");
}

void registerAll(alias thisModule)()
{
    alias members = Alias!(__traits(allMembers, thisModule));
    foreach(mem; members)
    {
        static if(mixin(`isCallable!(thisModule.`~mem~')'))
            registerFunction!(thisModule, mem)();
    }
    static if(__traits(hasMember, thisModule, "preInit"))
        preInit();
        
    module_init();

    foreach(mem; members)
    {
        static if(mixin(`!isCallable!(thisModule.`~mem~')'))
            registerModuleScopeSymbol!(mem, thisModule)();
    }

    static if(__traits(hasMember, thisModule, "postInit"))
        postInit();
}
