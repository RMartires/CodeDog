#xlator_CPP.py
import progSpec
import codeDogParser
from progSpec import cdlog, cdErr, logLvl
from codeGenerator import codeItemRef, codeUserMesg, codeStructFields, codeAllocater, appendGlobalFuncAcc, codeParameterList, makeTagText, codeAction, codeExpr, convertType

###### Routines to track types of identifiers and to look up type based on identifier.
def getContainerType(typeSpec, actionOrField):
    idxType=''
    if progSpec.isAContainer(typeSpec):
        containerTypeSpec = progSpec.getContainerSpec(typeSpec)
        if 'owner' in containerTypeSpec: owner=progSpec.getOwnerFromTypeSpec(containerTypeSpec)
        else: owner='me'
        if 'indexType' in containerTypeSpec:
            if 'IDXowner' in containerTypeSpec['indexType']:
                idxOwner=containerTypeSpec['indexType']['IDXowner'][0]
                idxType=containerTypeSpec['indexType']['idxBaseType'][0][0]
                idxType=applyOwner(idxOwner, idxType, '')
            else:
                idxType=containerTypeSpec['indexType']['idxBaseType'][0][0]
        if(isinstance(containerTypeSpec['datastructID'], str)):
            datastructID = containerTypeSpec['datastructID']
        else:   # it's a parseResult
            datastructID = containerTypeSpec['datastructID'][0]
        if idxType[0:4]=='uint': idxType+='_t'
        if(datastructID=='list'): datastructID = "deque"
        if(datastructID=='iterableList'): datastructID = "list"
    else:
        owner = progSpec.getOwnerFromTypeSpec(typeSpec)
        datastructID = 'None'
    return [datastructID, idxType, owner]

def adjustBaseTypes(fieldType):
    if(isinstance(fieldType, str)):
        if(fieldType=='uint8' or fieldType=='uint16'): fieldType='uint32'
        elif(fieldType=='int8' or fieldType=='int16'): fieldType='int32'
        if(fieldType=='uint32' or fieldType=='uint64' or fieldType=='int32' or fieldType=='int64'):
            langType=fieldType+'_t'
        else:
            langType=progSpec.flattenObjectName(fieldType)
    else: langType=progSpec.flattenObjectName(fieldType[0])
    return langType

def applyOwner(owner, langType, varMode):
    if owner=='me':
        langType = langType
    elif owner=='my':
        langType = "unique_ptr<"+langType + ' >'
    elif owner=='our':
        langType = "shared_ptr<"+langType + ' >'
    elif owner=='their':
        langType += '*'
    elif owner=='itr':
        langType += '::iterator'
    elif owner=='const':
        langType = "static const "+langType
    elif owner=='we':
        langType = 'static '+langType
    elif owner=='id_our':
        langType="shared_ptr<"+langType + ' >*'
    elif owner=='id_their':
        langType += '**'
    elif owner=='dblTheir':
        langType += '**'
    else:
        cdErr("ERROR: Owner of type not valid '" + owner + "'")
    return langType

def getUnwrappedClassOwner(classes, typeSpec, fieldType, varMode, ownerIn):
    ownerOut = ownerIn
    baseType = progSpec.isWrappedType(classes, fieldType)
    if baseType!=None:  # TODO: When this is all tested and stable, un-hardcode and optimize this!!!!!
        if 'ownerMe' in baseType:
            ownerOut = 'their'
        else:
            if varMode=='var' and progSpec.isOldContainerTempFunc(typeSpec):
                ownerOut=progSpec.getOwnerFromTypeSpec(baseType)   # TODO: remove this condition: accomodates old list type generated in stringStructs
            else:
                ownerOut=ownerIn
    return ownerOut

def getReqTagString(classes, typeSpec):
    reqTagString = ""
    reqTagList = progSpec.getReqTagList(typeSpec)
    if(reqTagList != None):
        reqTagString = "<"
        count = 0
        for reqTag in reqTagList:
            reqOwner = progSpec.getOwnerFromTemplateArg(reqTag)
            varTypeKeyword = progSpec.getTypeFromTemplateArg(reqTag)
            unwrappedOwner=getUnwrappedClassOwner(classes, typeSpec, varTypeKeyword, 'alloc', reqOwner)
            unwrappedTypeKeyword = progSpec.getUnwrappedClassFieldTypeKeyWord(classes, varTypeKeyword)
            unwrappedTypeKeyword = adjustBaseTypes(unwrappedTypeKeyword)
            reqType = applyOwner(unwrappedOwner, unwrappedTypeKeyword, '')
            if(count>0):reqTagString += ", "
            reqTagString += reqType
            count += 1
        reqTagString += ">"
    return reqTagString

def xlateLangType(classes, typeSpec, owner, fieldType, varMode, actionOrField, xlator):
    # varMode is 'var' or 'arg' or 'alloc'. Large items are passed as pointers
    langType = adjustBaseTypes(fieldType)
    InnerLangType = langType
    reqTagString = getReqTagString(classes, typeSpec)
    langType += reqTagString
    if reqTagString != '':InnerLangType = langType
    if varMode != 'alloc': langType = applyOwner(owner, langType, varMode)

    if progSpec.isNewContainerTempFunc(typeSpec): return [langType, InnerLangType]

    if progSpec.isAContainer(typeSpec):
        containerTypeSpec = progSpec.getContainerSpec(typeSpec)
        if(containerTypeSpec): # Make list, map, etc
            [containerType, idxType, idxOwner]=getContainerType(typeSpec, '')
            if 'owner' in containerTypeSpec:
                ctnrOwner = progSpec.getOwnerFromTypeSpec(containerTypeSpec)
            else: ctnrOwner='me'
            idxType  = adjustBaseTypes(idxType)
            if idxType=='timeValue': idxType = 'int64_t'
            if containerType=='deque':
                if varMode == 'alloc': langType = applyOwner(owner, langType, varMode)
                langType="deque< "+langType+" >"
            elif containerType=='list':
                if varMode == 'alloc': langType = applyOwner(owner, langType, varMode)
                langType="list< "+langType+" >"
            elif containerType=='map':
                if varMode == 'alloc': langType = applyOwner(owner, langType, varMode)
                langType="map< "+idxType+', '+langType+" >"
            elif containerType=='multimap':
                if varMode == 'alloc': langType = applyOwner(owner, langType, varMode)
                langType="multimap< "+idxType+', '+langType+" >"
            InnerLangType = langType
            if varMode != 'alloc':
                langType=applyOwner(ctnrOwner, langType, varMode)
    return [langType, InnerLangType]

def makePtrOpt(typeSpec):
    return('')

def codeIteratorOperation(itrCommand, fieldType):
    result = ''
    if(fieldType[0]=='deque'): # TODO: this should be like "If this iterator doesn't return BOTH key and value  ...". 'deque' is just one case.
        if itrCommand=='val':   result='*(%0)'
    else:
        if itrCommand=='goNext':  result='%0++'
        elif itrCommand=='goPrev':result='--%0'
        elif itrCommand=='key':   result='%0->first'
        elif itrCommand=='val':   result='%0->second'
    return result

def recodeStringFunctions(name, typeSpec):
    if name == "size": name = "length"
    elif name == "subStr": name = "substr"

    return [name, typeSpec]

def langStringFormatterCommand(fmtStr, argStr):
    S='strFmt('+'"'+ fmtStr +'"'+ argStr +')'
    return S

def LanguageSpecificDecorations(classes, S, typeSpec, owner, LorRorP_Val, xlator):
    return S

def checkForTypeCastNeed(lhsTypeSpec, rhsTypeSpec, RHScodeStr):
    return RHScodeStr

def getTheDerefPtrMods(itemTypeSpec):
    if itemTypeSpec!=None and isinstance(itemTypeSpec, dict) and 'owner' in itemTypeSpec:
        if progSpec.isNewContainerTempFunc(itemTypeSpec): return ['', '', False]
        if progSpec.typeIsPointer(itemTypeSpec):
            owner=progSpec.getTypeSpecOwner(itemTypeSpec)
            if progSpec.isAContainer(itemTypeSpec):
                if owner=='itr':
                    containerType = progSpec.getDatastructID(itemTypeSpec)
                    if containerType =='map' or containerType == 'multimap':
                        return ['', '->second', False]
                return ['(*', ')', False]
            else:
                if owner!='itr':
                    return ['(*', ')', True]
    return ['', '', False]

def derefPtr(varRef, itemTypeSpec):
    [leftMod, rightMod, isDerefd] = getTheDerefPtrMods(itemTypeSpec)
    S = leftMod + varRef + rightMod
    return [S, isDerefd]

def ChoosePtrDecorationForSimpleCase(owner):
    if(owner=='our' or owner=='my' or owner=='their'):
        return ['','->',  '(*', ')']
    else: return ['','.',  '','']

def chooseVirtualRValOwner(LVAL, RVAL):
    # Returns left and right text decorations for RHS of function arguments, return values, etc.
    if RVAL==0 or RVAL==None or isinstance(RVAL, str): return ['',''] # This happens e.g., string.size() # TODO: fix this.
    if LVAL==0 or LVAL==None or isinstance(LVAL, str): return ['', '']
    LeftOwner =progSpec.getTypeSpecOwner(LVAL)
    RightOwner=progSpec.getTypeSpecOwner(RVAL)
    if(LeftOwner=="id_their" and RightOwner=="id_their"): return ["&", ""]
    if LeftOwner == RightOwner: return ["", ""]
    if LeftOwner!='itr' and RightOwner=='itr':
        # TODO: test this change.  This looks like code that handled codeDog 1.0 container iterators, which is now handled in codeIteratorOperation()
        #return ["", "->second"]
        return ["", ""]
    if LeftOwner=='me' and progSpec.typeIsPointer(RVAL):
        return ["(*", "   )"]
    if progSpec.typeIsPointer(LVAL) and RightOwner=='me':
        return ["&", '']
    if LeftOwner=='their' and (RightOwner=='our' or RightOwner=='my'): return ['','.get()']
    return ['','']

def determinePtrConfigForNewVars(lhsTypeSpec, rhsTypeSpec, useCtor):
    leftOwner =progSpec.getTypeSpecOwner(lhsTypeSpec)
    rightOwner=progSpec.getTypeSpecOwner(rhsTypeSpec)
    if ((leftOwner=="me" or leftOwner=="literal") and rightOwner=="our"):
        return["*", ""]
    elif leftOwner=='their' and rightOwner == 'our' and not useCtor:
        return["*", ""]
    elif leftOwner=='their' and rightOwner == 'our' :
        return["", ".get()"]
    return["", ""]

def determinePtrConfigForAssignments(LVAL, RVAL, assignTag, codeStr):
    #TODO: make test case
    # Returns left and right text decorations for both LHS and RHS of assignment
    if RVAL==0 or RVAL==None or isinstance(RVAL, str): return ['','',  '',''] # This happens e.g., string.size() # TODO: fix this.
    if LVAL==0 or LVAL==None or isinstance(LVAL, str): return ['','',  '','']
    LeftOwner =progSpec.getTypeSpecOwner(LVAL)
    RightOwner=progSpec.getTypeSpecOwner(RVAL)
    if not isinstance(assignTag, str):
        assignTag = assignTag[0]
    if progSpec.typeIsPointer(LVAL) and progSpec.typeIsPointer(RVAL):
        if assignTag=='deep' :return ['(*',')',  '(*',')']
        elif LeftOwner=='their' and (RightOwner=='our' or RightOwner=='my'): return ['','', '','.get()']
        else: return ['','',  '', '']
    if LeftOwner == RightOwner: return ['','',  '','']
    if LeftOwner=='me' and progSpec.typeIsPointer(RVAL):
        [leftMod, rightMod, isDerefd] = getTheDerefPtrMods(RVAL)
        return ['','',  leftMod, rightMod]  # ['', '', "(*", ")"]
    if progSpec.typeIsPointer(LVAL) and RightOwner=='me':
        if assignTag!="" or assignTag=='deep':return ['(*',')',  '', '']
        else: return ['','',  "&", '']
    if progSpec.typeIsPointer(LVAL) and RightOwner=='literal':return ['(*',')',  '', '']
    if progSpec.typeIsPointer(LVAL) and RightOwner=='const':return ['(*',')', '','']
    return ['','',  '','']

def getCodeAllocStr(varTypeStr, owner):
    if(owner=='our'): S="make_shared<"+varTypeStr+">"
    elif(owner=='my'): S="make_unique<"+varTypeStr+">"
    elif(owner=='their'): S="new "+varTypeStr
    elif(owner=='me'): cdErr("Cannot allocate a 'me' variable. (" + varTypeStr + ')')
    elif(owner=='we'): cdErr("Cannot allocate a 'we' variable. (" + varTypeStr + ')')
    elif(owner=='const'): cdErr("Cannot allocate a 'const' variable.")
    else: cdErr("Cannot allocate variable because owner is " + owner+".")
    return S

def getCodeAllocSetStr(varTypeStr, owner, value):
    S=getCodeAllocStr(varTypeStr, owner)
    S+='('+value+')'
    return S

def getConstIntFieldStr(fieldName, fieldValue):
    S= "static const uint64_t "+fieldName+ " = " + fieldValue+ ";"
    return(S)

def getEnumStr(fieldName, enumList):
    S = "\n    enum " + fieldName +" {"
    enumSize = len (enumList)
    count=0
    for enumName in enumList:
        S += enumName+"="+hex(count)
        count=count+1
        if(count<enumSize): S += ", "
    S += "};\n";
    return(S)

def getEnumStringifyFunc(className, enumList):
    S = "deque<string> {}Strings = {{".format(className)
    S += '"{}"'.format('", "'.join(enumList))
    S += '};\n\n'
    return S

def codeIdentityCheck(S, S2, retType1, retType2, opIn):
    S2 = adjustQuotesForChar(retType1, retType2, S2)
    leftOwner  = progSpec.getTypeSpecOwner(retType1)
    rightOwner = progSpec.getTypeSpecOwner(retType2)
    if opIn == '===' or opIn == '!==':
        if progSpec.typeSpecsAreCompatible(retType1, retType2):
            return S+ opIn[:2] +S2
        elif progSpec.typeIsPointer(retType1) and progSpec.typeIsPointer(retType2):
            if leftOwner =='our' or leftOwner =='my': S+='.get()'
            if rightOwner=='our' or rightOwner=='my': S2+='.get()'
            return "(void*)("+ S +") "+opIn[:2]+" (void*)("+S2+")"
        else:
            return S+ opIn[:2] +S2
    else:
        if (opIn == '=='): opOut=' == '
        elif (opIn == '!='): opOut=' != '
        if not(leftOwner=='itr' and rightOwner=='itr'):
            [S_derefd, isDerefd] = derefPtr(S, retType1)
            if S2!='NULL' and S2!='nullptr': S=S_derefd
            [S2, isDerefd]=derefPtr(S2, retType2)
        return S+ opOut+S2
    return S

def codeComparisonStr(S, S2, retType1, retType2, op):
    if (op == '<'): S+=' < '
    elif (op == '>'): S+=' > '
    elif (op == '<='): S+=' <= '
    elif (op == '>='): S+=' >= '
    else: print("ERROR: One of <, >, <= or >= expected in code generator."); exit(2)
    S2 = adjustQuotesForChar(retType1, retType2, S2)
    [S2, isDerefd]=derefPtr(S2, retType2)
    S+=S2
    return S

###################################################### CONTAINERS
def getContaineCategory(containerSpec):
    fTypeKW = progSpec.fieldTypeKeyword(containerSpec)
    if fTypeKW=='DblLinkedList':
        return 'DblLinkedList'
    elif fTypeKW=='multimap' or fTypeKW=='map' or fTypeKW=='CPP_Map' or fTypeKW=='RBTreeMap':
        return 'MAP'
    elif fTypeKW=='list':
        return 'LIST'
    elif fTypeKW=='deque' or fTypeKW=='CPP_Deque':
        return 'DEQUE'
    elif 'Multimap' in fTypeKW:
        return 'MULTIMAP'
    return None

def getContainerTypeInfo(classes, containerType, name, idxType, typeSpecIn, paramList, genericArgs, xlator):
    convertedIdxType = ""
    typeSpecOut = typeSpecIn
    if progSpec.isNewContainerTempFunc(typeSpecIn): return(name, typeSpecOut, paramList, convertedIdxType)
    if containerType=='deque' or  containerType=='list':
        if name=='at' or name=='resize': pass
        elif name=='size' : typeSpecOut={'owner':'me', 'fieldType': 'uint32'}
        elif name=='insert'   : typeSpecOut={'owner':'me', 'fieldType': 'void', 'argList':[{'typeSpec':{'owner':'itr'}}, {'typeSpec':typeSpecIn}]}
        elif name=='insertIdx': typeSpecOut={'owner':'me', 'fieldType': 'void', 'argList':[{'typeSpec':{'owner':'itr'}}, {'typeSpec':typeSpecIn}]}; typeSpecOut['codeConverter']='%0.insert((%0.begin()+%1), %2)'
        elif name=='InsertIdx': typeSpecOut={'owner':'me', 'fieldType': 'void', 'argList':[{'typeSpec':{'owner':'itr'}}, {'typeSpec':typeSpecIn}]}; typeSpecOut['codeConverter']='%0->insert((%0->begin()+%1), %2)'
        elif name=='clear'    : typeSpecOut={'owner':'me', 'fieldType': 'void'}
        elif name=='erase'    : name='erase';  typeSpecOut['owner']='itr';
        elif name=='deleteNth': typeSpecOut['codeConverter']='%0->erase(%0->begin()+%1)'; typeSpecOut['owner']='itr';
        elif name=='DeleteNth': typeSpecOut['codeConverter']='%0.erase(%0.begin()+%1)'; typeSpecOut['owner']='itr';
        elif name=='front'    : name='begin()';  typeSpecOut['owner']='itr'; paramList=None;
        elif name=='back'     : name='rbegin()'; typeSpecOut['owner']='itr'; paramList=None;
        elif name=='end'      : name='end()';    typeSpecOut['owner']='itr'; paramList=None;
        elif name=='rend'     : name='rend()';   typeSpecOut['owner']='itr'; paramList=None;
        elif name=='nthItr'   : typeSpecOut['codeConverter']='(%0->begin()+%1)'; typeSpecOut['owner']='itr';
        elif name=='first'    : name='front()';  paramList=None;
        elif name=='last'     : name='back()';   paramList=None;
        elif name=='popFirst' : name='pop_front'
        elif name=='popLast'  : name='pop_back'
        elif name=='pushFirst': name='push_front';# typeSpecOut={'owner':'me', 'fieldType': 'void', 'argList':[{'typeSpec':typeSpecIn}]}
        elif name=='pushLast' : name='push_back'; # typeSpecOut={'owner':'me', 'fieldType': 'void', 'argList':[{'typeSpec':typeSpecIn}]}
        elif name=='isEmpty'  : name='empty';     typeSpecOut={'owner':'me', 'fieldType': 'bool'}
        elif name=='itmMode'  or name=='tag' or name=='value'  or name=='format' or name=='itmItr' or True: pass # temp fix
        else: print("Unknown deque or list command:", containerType + '::' +name); exit(2);
    elif containerType=='map':
        if idxType=='timeValue': convertedIdxType = 'int64_t'
        else: convertedIdxType=adjustBaseTypes(idxType)
        [convertedItmType, innerType] = convertType(typeSpecOut, 'var', '', genericArgs, xlator)
        if name=='at': pass
        elif name=='containsKey'   :  typeSpecOut={'owner':'me', 'fieldType': 'bool'}; typeSpecOut['codeConverter']='(%0.count(%1)>0)';
        elif name=='containsKey2'   :  typeSpecOut={'owner':'me', 'fieldType': 'bool'}; typeSpecOut['codeConverter']='(%0->count(%1)>0)';
        elif name=='size'     : typeSpecOut={'owner':'me', 'fieldType': 'uint32'}
        elif name=='insert'   : typeSpecOut['codeConverter']='insert(pair<'+convertedIdxType+', '+convertedItmType+'>(%1, %2))';
        elif name=='clear'    : typeSpecOut={'owner':'me', 'fieldType': 'void'}
        elif name=='find'     : name='find';     typeSpecOut['owner']='itr'; typeSpecOut['fieldType']=convertedItmType;
        elif name=='lower_bound'     : name='lower_bound';     typeSpecOut['owner']='itr'; typeSpecOut['fieldType']=convertedItmType;
        elif name=='get'      : name='at';    # typeSpecOut['owner']='me';  typeSpecOut['fieldType']=convertedItmType;
        elif name=='erase'    : name='erase';  typeSpecOut['owner']='itr';
        elif name=='front'    : name='begin()';  typeSpecOut['owner']='itr'; paramList=None;
        elif name=='back'     : name='rbegin()'; typeSpecOut['owner']='itr'; paramList=None;
        elif name=='end'      : name='end()';    typeSpecOut['owner']='itr'; paramList=None;
        elif name=='rend'     : name='rend()';   typeSpecOut['owner']='itr'; paramList=None;
        elif name=='first'    : name='begin()->second';  paramList=None;
        elif name=='last'     : name='rbegin()->second'; paramList=None;
        elif name=='popFirst' : name='pop_front'
        elif name=='popLast'  : name='pop_back'
        elif name=='isEmpty'  : name='empty';     typeSpecOut={'owner':'me', 'fieldType': 'bool'}
        else: print("Unknown map command:", name); exit(2);
    elif containerType=='multimap':
        if idxType=='timeValue': convertedIdxType = 'int64_t'
        else: convertedIdxType=adjustBaseTypes(idxType)
        [convertedItmType, innerType] = convertType(typeSpecOut, 'var', '', genericArgs, xlator)
        if name=='at': pass
        elif name=='containsKey'   :  typeSpecOut={'owner':'me', 'fieldType': 'bool'}; typeSpecOut['codeConverter']='count(%1)>=1';
        elif name=='size'     : typeSpecOut={'owner':'me', 'fieldType': 'uint32'}
        elif name=='insert'   : typeSpecOut['codeConverter']='insert(pair<'+convertedIdxType+', '+convertedItmType+'>(%1, %2))';
        elif name=='clear'    : typeSpecOut={'owner':'me', 'fieldType': 'void'}
        elif name=='find'     : name='find';     typeSpecOut['owner']='itr'; typeSpecOut['fieldType']=convertedItmType;
        elif name=='erase'    : name='erase';  typeSpecOut['owner']='itr';
        elif name=='front'    : name='begin()';  typeSpecOut['owner']='itr'; paramList=None;
        elif name=='back'     : name='rbegin()'; typeSpecOut['owner']='itr'; paramList=None;
        elif name=='end'      : name='end()';    typeSpecOut['owner']='itr'; paramList=None;
        elif name=='rend'     : name='rend()';   typeSpecOut['owner']='itr'; paramList=None;
        elif name=='first'    : name='begin()->second';  paramList=None;
        elif name=='last'     : name='rbegin()->second'; paramList=None;
        elif name=='popFirst' : name='%0.erase(%0.begin())'; paramList=None;
        elif name=='popLast'  : name='pop_back'
        elif name=='isEmpty'  : name='empty';     typeSpecOut={'owner':'me', 'fieldType': 'bool'}
        else: print("Unknown multimap command:", name); exit(2);
    elif containerType=='tree': # TODO: Make trees work
        if name=='insert' or name=='erase': pass
        elif name=='size' : typeSpecOut={'owner':'me', 'fieldType': 'uint32'}
        elif name=='clear': typeSpecOut={'owner':'me', 'fieldType': 'void'}
        else: print("Unknown tree command:", name); exit(2)
    elif containerType=='graph': # TODO: Make graphs work
        if name=='insert' or name=='erase': pass
        elif name=='size' : typeSpecOut={'owner':'me', 'fieldType': 'uint32'}
        elif name=='clear': typeSpecOut={'owner':'me', 'fieldType': 'void'}
        else: print("Unknown graph command:", name); exit(2);
    elif containerType=='stream': # TODO: Make stream work
        pass
    elif containerType=='filesystem': # TODO: Make filesystem work
        pass
    else: print("Unknown container type:", containerType); exit(2);
    return(name, typeSpecOut, paramList, convertedIdxType)

def codeArrayIndex(idx, containerType, LorR_Val, previousSegName, idxTypeSpec):
    if 'owner' in idxTypeSpec and (idxTypeSpec['owner']=='their' or idxTypeSpec['owner']=='our' or idxTypeSpec['owner']=='itr'):
        idx = "*"+idx
    S= '[' + idx +']'
    return S
###################################################### CONTAINER REPETITIONS
def codeRangeSpec(traversalMode, ctrType, repName, S_low, S_hi, indent, xlator):
    if(traversalMode=='Forward' or traversalMode==None):
        S = indent + "for("+ctrType+" " + repName+'='+ S_low + "; " + repName + "!=" + S_hi +"; "+ codeIncrement(repName) + "){\n"
    elif(traversalMode=='Backward'):
        S = indent + "for("+ctrType+" " + repName+'='+ S_hi + "-1; " + repName + ">=" + S_low +"; --"+ repName + "){\n"
    return (S)

def iterateRangeContainerStr(classes,localVarsAlloc,StartKey,EndKey,ctnrTSpec,ctnrOwner,repName,ctnrName,datastructID,idxTypeKW,indent,xlator):
    willBeModifiedDuringTraversal=True   # TODO: Set this programatically later.
    actionText       = ""
    loopCounterName  = ""
    ctnrOwner        = progSpec.getContainerFirstElementOwner(ctnrTSpec)
    containedType    = progSpec.getFieldTypeKeyWordOld(ctnrTSpec)
    ctrlVarsTypeSpec = {'owner':ctnrOwner, 'fieldType':containedType}
    itrName          = repName + "Itr"
    if progSpec.ownerIsPointer(ctnrOwner): connector="->"
    else: connector = "."
    reqTagList       = progSpec.getReqTagList(ctnrTSpec)
    containerCat     = getContaineCategory(ctnrTSpec)
    if containerCat=="MAP" or containerCat=="MULTIMAP":
        if(reqTagList != None):
            ctrlVarsTypeSpec['owner']     = progSpec.getOwnerFromTemplateArg(reqTagList[1])
            ctrlVarsTypeSpec['fieldType'] = progSpec.getTypeFromTemplateArg(reqTagList[1])
        keyVarSpec = {'owner':'itr', 'fieldType':containedType, 'codeConverter':(repName+'.first')}
        loopCounterName  = repName+'_key'
        ctrlVarsTypeSpec['codeConverter'] = (repName+'.second')
        localVarsAlloc.append([loopCounterName, keyVarSpec])  # Tracking local vars for scope
        localVarsAlloc.append([repName, ctrlVarsTypeSpec]) # Tracking local vars for scope
        actionText += (indent + "for( auto " + itrName+' ='+ ctnrName+connector+'lower_bound('+StartKey+')' + "; " + itrName + " !=" + ctnrName+connector+'upper_bound('+EndKey+')' +"; ++"+ repName + "Itr ){\n"
                    + indent+"    "+"auto "+repName+" = *"+itrName+";\n")
    elif datastructID=='list' or (datastructID=='deque' and not willBeModifiedDuringTraversal): pass;
    elif datastructID=='deque' and willBeModifiedDuringTraversal: pass;
    else:
        print("DSID iterateRangeContainerStr:",datastructID,containerCat)
        exit(2)
    return [actionText, loopCounterName]

def iterateContainerStr(classes,localVarsAlloc,ctnrTSpec,repName,ctnrName,isBackward,indent,genericArgs,xlator):
    #TODO: handle isBackward
    willBeModifiedDuringTraversal=True   # TODO: Set this programatically later.
    [datastructID, idxTypeKW, ctnrOwner]=getContainerType(ctnrTSpec, 'action')
    actionText       = ""
    loopCounterName  = repName+'_key'
    owner            = progSpec.getContainerFirstElementOwner(ctnrTSpec)
    containedType    = progSpec.getFieldTypeKeyWordOld(ctnrTSpec)
    ctrlVarsTypeSpec = {'owner':owner, 'fieldType':containedType}
    reqTagList       = progSpec.getReqTagList(ctnrTSpec)
    [LDeclP, RDeclP, LDeclA, RDeclA] = ChoosePtrDecorationForSimpleCase(ctnrOwner)
    itrTypeSpec      = progSpec.getItrTypeOfDataStruct(datastructID, ctnrTSpec)
    itrFieldType     = progSpec.fieldTypeKeyword(itrTypeSpec)
    itrOwner         = progSpec.getOwnerFromTypeSpec(itrTypeSpec)
    [LNodeP, RNodeP, LNodeA, RNodeA] = ChoosePtrDecorationForSimpleCase(itrOwner)
    itrName          = repName + "Itr"
    containerCat     = getContaineCategory(ctnrTSpec)
    itrIncStr        = ""
    if containerCat=='DblLinkedList':
        ctrlVarsTypeSpec = {'owner':'our', 'fieldType':['infon']}
        keyVarSpec = {'owner':'me', 'fieldType':'uint64_t'}
        localVarsAlloc.append([loopCounterName, keyVarSpec])  # Tracking local vars for scope
        localVarsAlloc.append([repName, ctrlVarsTypeSpec]) # Tracking local vars for scope
        actionText += (indent + "for( auto " + itrName+' ='+ ctnrName+RDeclP+'begin()' + "; " + itrName + " !=" + ctnrName+RDeclP+'end()' +"; "+ itrName + " = " + itrName+"->next ){\n"
                    + indent+"    "+"shared_ptr<infon> "+repName+" = "+itrName+"->pItem;\n")
        return [actionText, loopCounterName, itrIncStr]
    if containerCat=='MAP':
        if(reqTagList != None):
            ctrlVarsTypeSpec['owner']     = progSpec.getOwnerFromTemplateArg(reqTagList[1])
            ctrlVarsTypeSpec['fieldType'] = progSpec.getTypeFromTemplateArg(reqTagList[1])
        keyVarSpec  = {'owner':'me', 'fieldType':containedType, 'codeConverter':(repName+'.first')}
        localVarsAlloc.append([loopCounterName, keyVarSpec])  # Tracking local vars for scope
        getNodeVal  = progSpec.getCodeConverterByFieldID(classes, itrFieldType, "val", repName,RNodeP)
        ctrlVarsTypeSpec['codeConverter'] = (getNodeVal)
        localVarsAlloc.append([repName, ctrlVarsTypeSpec]) # Tracking local vars for scope
        frontItr    = progSpec.getCodeConverterByFieldID(classes, datastructID, "front" , ctnrName , RDeclP)
        actionText += (indent + "for( auto " + itrName+' ='+frontItr + "; " + itrName + " !=" + ctnrName+RDeclP+'end()' +"; ++"+itrName  + " ){\n"
                    + indent+"    "+"auto "+repName+" = *"+itrName+";\n")
    elif containerCat=='LIST' or (datastructID=='deque' and not willBeModifiedDuringTraversal):
        keyVarSpec = {'owner':owner, 'fieldType':containedType}
        localVarsAlloc.append([loopCounterName, keyVarSpec])  # Tracking local vars for scope
        localVarsAlloc.append([repName, ctrlVarsTypeSpec]) # Tracking local vars for scope
        if isBackward:
            actionText += (indent + "for( auto " + itrName+' ='+ ctnrName+RDeclP+'rbegin()' + "; " + itrName + " !=" + ctnrName+RDeclP+'rend()' +"; ++"+ itrName + " ){\n")
        else:
            actionText += (indent + "for( auto " + itrName+' ='+ ctnrName+RDeclP+'begin()' + "; " + itrName + " !=" + ctnrName+RDeclP+'end()' +"; ++"+ itrName + " ){\n")
        actionText += indent+"    "+"auto "+repName+" = *"+itrName+";\n"
    elif (datastructID=='deque' or datastructID=='CPP_Deque' ) and willBeModifiedDuringTraversal:
        keyVarSpec = {'owner':'me', 'fieldType':'uint64_t'}
        localVarsAlloc.append([loopCounterName, keyVarSpec])  # Tracking local vars for scope
        localVarsAlloc.append([repName, ctrlVarsTypeSpec]) # Tracking local vars for scope
        lvName=repName+"Idx"
        if isBackward:
            actionText += (indent + "for( int64_t " + lvName+' = '+ctnrName+RDeclP+'size()-1; ' + lvName+" >= 0; "+" --"+lvName+" ){\n")
        else:
            actionText += (indent + "for( uint64_t " + lvName+' = 0; ' + lvName+" < " +  ctnrName+RDeclP+'size();' +" ++"+lvName+" ){\n")
        actionText += indent+"    "+"auto &"+repName+" = "+LDeclA+ctnrName+RDeclA+"["+lvName+"];\n"
    else: cdErr("iterateContainerStr() datastructID = " + datastructID)
    return [actionText, loopCounterName, itrIncStr]
###################################################### EXPRESSION CODING
def codeFactor(item, objsRefed, returnType, expectedTypeSpec, LorRorP_Val, genericArgs, xlator):
    ####  ( value | ('(' + expr + ')') | ('!' + expr) | ('-' + expr) | varRef("varFunRef"))
    #print('                  factor: ', item)
    S=''
    retTypeSpec='noType'
    item0 = item[0]
    #print("ITEM0=", item0, ">>>>>", item)
    if (isinstance(item0, str)):
        if item0=='(':
            [S2, retTypeSpec] = codeExpr(item[1], objsRefed, returnType, expectedTypeSpec, LorRorP_Val, genericArgs, xlator)
            S+='(' + S2 +')'
        elif item0=='!':
            [S2, retTypeSpec] = codeExpr(item[1], objsRefed, returnType, expectedTypeSpec, LorRorP_Val, genericArgs, xlator)
            S+='!' + S2
        elif item0=='-':
            [S2, retTypeSpec] = codeExpr(item[1], objsRefed, returnType, expectedTypeSpec, LorRorP_Val, genericArgs, xlator)
            S+='-' + S2
        elif item0=='[':
            tmp="{"
            for expr in item[1:-1]:
                [S2, retTypeSpec] = codeExpr(expr, objsRefed, returnType, expectedTypeSpec, LorRorP_Val, genericArgs, xlator)
                if len(tmp)>1: tmp+=", "
                tmp+=S2
            tmp+="}"
            S+=tmp
        elif item0=='{':
            tmp="{"
            idx=1
            while idx <  len(item)-1:
                valExpr = item[idx+2]
                [S2, retTypeSpec] = codeExpr(valExpr, objsRefed, returnType, expectedTypeSpec, LorRorP_Val, genericArgs, xlator)
                if len(tmp)>1: tmp+=", "
                tmp+="{" + item[idx] + ", " + S2 + "}"
                idx += 3
            tmp+="}"
            S+=tmp
        else:
            expected_KeyType = progSpec.varTypeKeyWord(expectedTypeSpec)
            if expected_KeyType == "BigInt":
                S += item0
                retTypeSpec='BigInt'
            elif expected_KeyType == "BigFloat":
                S += item0 + "_mpf"
                retTypeSpec='BigFloat'
            elif expected_KeyType == "BigFrac":
                S += item0 + "_mpq"
                retTypeSpec='BigFrac'
            elif(item0[0]=="'"):
                retTypeSpec='string'
                S+=codeUserMesg(item0[1:-1], xlator)
            elif (item0[0]=='"'):
                retTypeSpec='string'
                if returnType != None and returnType["fieldType"]=="char":
                    retTypeSpec='char'
                    innerS=item0[1:-1]
                    if len(innerS)==1:
                        S+="'"+item0[1:-1] +"'"
                    else:
                        cdErr("Characters must have exactly 1 character.")
                else:
                    S+='"'+item0[1:-1] +'"'
                    retTypeSpec='string'
            else:
                S+=item0;
                if item0=='false' or item0=='true':
                    retTypeSpec={'owner': 'literal', 'fieldType': 'bool'}
                if retTypeSpec == 'noType' and progSpec.isStringNumeric(item0):
                    retTypeSpec={'owner': 'literal', 'fieldType': 'numeric'}
                if retTypeSpec == 'noType' and progSpec.typeIsInteger(expected_KeyType):retTypeSpec=expected_KeyType
                if retTypeSpec == 'noType' and progSpec.isStringNumeric(item0):retTypeSpec={'owner': 'literal', 'fieldType': 'numeric'}
    else: # CODEDOG LITERALS
        if isinstance(item0[0], str):
            S+=item0[0]
            if '"' in S or "'" in S: retTypeSpec = 'string'
            if '.' in S: retTypeSpec = 'double'
            if isinstance(S, int): retTypeSpec = 'int64'
            else:  retTypeSpec = 'int32'
        else:
            [codeStr, retTypeSpec, prntType, AltIDXFormat]=codeItemRef(item0, 'RVAL', objsRefed, returnType, LorRorP_Val, genericArgs, xlator)
            if(codeStr=="NULL"):
                codeStr="nullptr"
                retTypeSpec={'owner':"PTR"}
            S+=codeStr                                # Code variable reference or function call
    return [S, retTypeSpec]

######################################################
def adjustQuotesForChar(typeSpec1, typeSpec2, S):
    fieldType1 = progSpec.fieldTypeKeyword(typeSpec1)
    fieldType2 = progSpec.fieldTypeKeyword(typeSpec2)
    if fieldType1 == "char" and (fieldType2 == 'string' or fieldType2 == 'String') and S[0] == '"':
        return("'" + S[1:-1] + "'")
    return(S)

def adjustConditional(S2, conditionType):
    return [S2, conditionType]

def codeSpecialReference(segSpec, objsRefed, genericArgs, xlator):
    S=''
    fieldType='void'   # default to void
    retOwner='me'    # default to 'me'
    funcName=segSpec[0]
    if(len(segSpec)>2):  # If there are arguments...
        paramList=segSpec[2]
        if(funcName=='print'):
            # TODO: have a tag to choose cout vs printf()
            S+='cout'
            for P in paramList:
                [S2, argTypeSpec]=codeExpr(P[0], objsRefed, None, None, 'PARAM', genericArgs, xlator)
                [S2, isDerefd]=derefPtr(S2, argTypeSpec)
                S+=' << '+S2
            S+=" << flush"
        elif(funcName=='input'):
            P=paramList[0]
            [S2, argTypeSpec]=codeExpr(P[0], objsRefed, None, None, 'PARAM', genericArgs, xlator)
            [S2, isDerefd]=derefPtr(S2, argTypeSpec)
            S+='getline(cin, '+S2+')'
        elif(funcName=='AllocateOrClear'):
            [varName,  varTypeSpec]=codeExpr(paramList[0][0], objsRefed, None, None, 'PARAM', genericArgs, xlator)
            if(varTypeSpec==0): cdErr("Name is undefined: " + varName)
            S+='if('+varName+'){'+varName+'->clear();} else {'+varName+" = "+codeAllocater(varTypeSpec, genericArgs, xlator)+"();}"
        elif(funcName=='Allocate'):
            [varName,  varTypeSpec]=codeExpr(paramList[0][0], objsRefed, None, None, 'LVAL', genericArgs, xlator)
            if(varTypeSpec==0): cdErr("Name is Undefined: " + varName)
            S+=varName+" = "+codeAllocater(varTypeSpec, genericArgs, xlator)+'('
            count=0   # TODO: As needed, make this call CodeParameterList() with modelParams of the constructor.
            for P in paramList[1:]:
                if(count>0): S+=', '
                [S2, argTypeSpec]=codeExpr(P[0], objsRefed, None, None, 'PARAM', genericArgs, xlator)
                S+=S2
                count=count+1
            S+=")"
        elif(funcName=='callPeriodically'):
            [objName,  typeSpec]=codeExpr(paramList[1][0], objsRefed, None, None, 'PARAM', genericArgs, xlator)
            [interval,  intTypeSpec]   =codeExpr(paramList[2][0], objsRefed, None, None, 'PARAM', genericArgs, xlator)
            fieldType = progSpec.fieldTypeKeyword(typeSpec)
            varTypeSpec= fieldType
            wrapperName="cb_wraps_"+varTypeSpec
            S+='g_timeout_add('+interval+', '+wrapperName+', '+objName+')'

            # Create a global function wrapping the class
            decl='\nint '+wrapperName+'(void* data)'
            defn='{'+varTypeSpec+'* self = ('+varTypeSpec+'*)data; self->run(); return true;}\n\n'
            appendGlobalFuncAcc(decl, defn)
        elif(funcName=='break'):
            if len(paramList)==0: S='break'
        elif(funcName=='return'):
            if len(paramList)==0: S+='return'
        elif(funcName=='toStr'):
            if len(paramList)==1:
                [S2, argTypeSpec]=codeExpr(P[0][0], objsRefed, None, None, 'PARAM', genericArgs, xlator)
                [S2, isDerefd]=derefPtr(S2, argTypeSpec)
                S+='to_string('+S2+')'
                fieldType='string'
        elif(funcName=='asClass'):
            if len(paramList)==2:
                [newTypeStr, argTypeSpec]=codeExpr(paramList[0][0], objsRefed, None, None, 'PARAM', genericArgs, xlator)
                [newTypeStr, isDerefd]=derefPtr(newTypeStr, argTypeSpec)
                [toCvtStr, toCvtTypeSpec]=codeExpr(paramList[1][0], objsRefed, None, None, 'PARAM', genericArgs, xlator)
               # [toCvtStr, isDerefd]=derefPtr(toCvtStr, toCvtTypeSpec)
                varOwner=progSpec.getTypeSpecOwner(toCvtTypeSpec)
                if(varOwner=='their'): S="static_cast<"+newTypeStr+"*>("+toCvtStr+")"
                elif(varOwner=='our'): S="static_pointer_cast<"+newTypeStr+">("+toCvtStr+")"
                elif(varOwner=='my'):  S="static_pointer_cast<"+newTypeStr+">("+toCvtStr+")"
                elif(varOwner=='me'):  S="static_cast<"+newTypeStr+">("+toCvtStr+")"
                else: cdErr("Casting that to "+str(newTypeStr)+" is not yet supported.")
                fieldType = newTypeStr
                retOwner= varOwner

    else: # Not parameters, i.e., not a function
        if(funcName=='self'):
            S+='this'

    return [S, retOwner, fieldType]

def checkIfSpecialAssignmentFormIsNeeded(AltIDXFormat, RHS, rhsType, LHS, LHSParentType, LHS_FieldType):
    # Check for string A[x] = B;  If so, render A.insert(B,x)
    S = ''
    [containerType, idxType, owner]=getContainerType(AltIDXFormat[1], "")
    if containerType == 'RBTreeMap':
        S=AltIDXFormat[0] + '.insert(' + AltIDXFormat[2] + ', ' + RHS + ');\n'
    return S

############################################
def codeMain(classes, tags, objsRefed, xlator):
    cdlog(3, "\n            Generating GLOBAL...")
    if("GLOBAL" in classes[1]):
        if(classes[0]["GLOBAL"]['stateType'] != 'struct'):
            print("ERROR: GLOBAL must be a 'struct'.")
            exit(2)
        [structCode, funcCode, globalFuncs]=codeStructFields(classes, "GLOBAL", tags, '', objsRefed, xlator)
        if(funcCode==''): funcCode="// No main() function.\n"
        if(structCode==''): structCode="// No Main Globals.\n"
        funcCode = "\n\n"+funcCode
        return ["\n\n// Globals\n" + structCode + "\n// Global Functions\n" + globalFuncs, funcCode]
    return ["// No Main Globals.\n", "// No main() function defined.\n"]

def codeArgText(argFieldName, argType, argOwner, typeSpec, makeConst, typeArgList, xlator):
    argTypeStr = argType
    if makeConst:
        if argOwner == "me": argMod = "&"
        else: argMod = ""
        argTypeStr = "const "+argTypeStr+argMod
    return argTypeStr + " " +argFieldName

def codeStructText(classes, attrList, parentClass, classInherits, classImplements, structName, structCode, tags):
    if parentClass != "":
        parentClass = parentClass.replace('::', '_')
        parentClass = progSpec.getUnwrappedClassFieldTypeKeyWord(classes, structName)
        parentClass=': public '+parentClass+' '
        print("Warning: old style inheritance used: " , parentClass)
    if classInherits!=None:
        parentClass=': public '
        count =0
        for item in classInherits[0]:
            if count>0:
                parentClass+= ', '
            parentClass+= progSpec.getUnwrappedClassFieldTypeKeyWord(classes, item)
            count += 1
    S= "\nstruct "+structName+parentClass+"{\n" + structCode + '};\n'
    typeArgList = progSpec.getTypeArgList(structName)
    templateHeader = ""
    if(typeArgList != None):
        forwardDecls = ""
        templateHeader = codeTemplateHeader(structName, typeArgList)+" "
        S=templateHeader+S
    forwardDecls=templateHeader+"struct " + structName + ";  \t// Forward declaration\n"
    return([S,forwardDecls])

def produceTypeDefs(typeDefMap, xlator):
    typeDefCode="\n// Typedefs:\n"
    for key in typeDefMap:
        val=typeDefMap[key]
        #sprint '['+key+']='+val+']'
        if(val != '' and val != key):
            typeDefCode += 'typedef '+key+' '+val+';\n'
    return typeDefCode

def addSpecialCode(filename):
    S='\n\n//////////// C++ specific code:\n'
    S += "\n\nusing namespace std;\n\n"
    S += 'const string filename = "' + filename + '";\n'
    S += r'static void reportFault(int Signal){cout<<"\nSegmentation Fault.\n"; fflush(stdout); abort();}'+'\n\n'

    S += "string enumText(string* array, int enumVal, int enumOffset){return array[enumVal >> enumOffset];}\n";
    S += "#define SetBits(item, mask, val) {(item) &= ~((uint64_t)mask); (item)|=((uint64_t)val);}\n"

    S+="""
    // Thanks to Erik Aronesty via stackoverflow.com
    // Like printf but returns a string.
    // #include <memory>, #include <cstdarg>
    inline std::string strFmt(const std::string fmt_str, ...) {
        int final_n, n = fmt_str.size() * 2; /* reserve 2 times as much as the length of the fmt_str */
        std::string str;
        std::unique_ptr<char[]> formatted;
        va_list ap;
        while(1) {
            formatted.reset(new char[n]); /* wrap the plain char array into the unique_ptr */
            strcpy(&formatted[0], fmt_str.c_str());
// WINDOWS: strcpy_s(&formatted[0], n, fmt_str.c_str());
            va_start(ap, fmt_str);
            final_n = vsnprintf(&formatted[0], n, fmt_str.c_str(), ap);
            va_end(ap);
            if (final_n < 0 || final_n >= n)
                n += abs(final_n - n + 1);
            else
                break;
        }
        return std::string(formatted.get());
    }

    string getFilesDirAsString(){
        string fileDir = "./";
        mkdir(fileDir.data(), S_IRWXU | S_IRWXG | S_IROTH | S_IXOTH);
// WINDOWS: _mkdir(fileDir.data());
        return (fileDir);
    }
    string getAssetsDir(){
        string fileDir = "./assets";
        mkdir(fileDir.data(), S_IRWXU | S_IRWXG | S_IROTH | S_IXOTH);
        return (fileDir);
    }
    bool doesFileExist(string filePath){
        ifstream ifile(filename);
        return (bool)ifile;
    }

    void copyAssetToWritableFolder(string fromPath, string toPath){
        //TODO: finish func body if package C++
    }

    string joinCmdStrings(int count , char *argv[]) {
        string acc="";
        for(int i=1; i<count; ++i){
            if(i>1) acc+=" ";
            acc += argv[i];
        }
        return(acc);
    }

    """

    decl ="string readFileAsString(string filename)"
    defn="""{
        string S="";
        std::ifstream file(filename);
        if(file.eof() || file.fail()) {return "";}
        file.seekg(0, std::ios::end);
        S.resize(file.tellg());
        file.seekg(0, std::ios::beg);
        file.read((char*)S.c_str(), S.length());
        return S;  //No errors
    }

    """
    appendGlobalFuncAcc(decl, defn)

    return S

def addGLOBALSpecialCode(classes, tags, xlator):
    specialCode =''

    GLOBAL_CODE="""
struct GLOBAL{
    %s
}
    """ % (specialCode)

    #codeDogParser.AddToObjectFromText(classes[0], classes[1], GLOBAL_CODE )

def codeNewVarStr(classes, tags, lhsTypeSpec, varName, fieldDef, indent, objsRefed, actionOrField, genericArgs, localVarsAllocated, xlator):
    varDeclareStr = ''
    assignValue   = ''
    isAllocated   = fieldDef['isAllocated']
    owner         = progSpec.getTypeSpecOwner(lhsTypeSpec)
    useCtor       = False
    if fieldDef['paramList'] and fieldDef['paramList'][-1] == "^&useCtor//8":
        del fieldDef['paramList'][-1]
        useCtor = True
    [convertedType, innerType] = convertType(lhsTypeSpec, 'var', actionOrField, genericArgs, xlator)
    localVarsAllocated.append([varName, lhsTypeSpec])  # Tracking local vars for scope
    if(fieldDef['value']):
        [RHS, rhsTypeSpec]=codeExpr(fieldDef['value'][0], objsRefed, lhsTypeSpec, None, 'RVAL', genericArgs, xlator)
        [LHS_leftMod, LHS_rightMod,  RHS_leftMod, RHS_rightMod] = determinePtrConfigForAssignments(lhsTypeSpec, rhsTypeSpec, "" , RHS)
        if(isAllocated and not progSpec.typeIsPointer(rhsTypeSpec)): RHS = getCodeAllocSetStr(innerType, owner, RHS)
        else: RHS = RHS_leftMod+RHS+RHS_rightMod
        if(isAllocated or useCtor==False): assignValue = " = " + RHS
        else: assignValue = RHS

    else: # If no value was given:
        CPL=''
        if fieldDef['paramList'] != None:       # call constructor  # curly bracket param list
            # Code the constructor's arguments
            [CPL, paramTypeList] = codeParameterList(varName, fieldDef['paramList'], None, objsRefed, genericArgs, xlator)
            if len(paramTypeList)==1:
                if not isinstance(paramTypeList[0], dict):
                    print("\nPROBLEM: The return type of the parameter '", CPL, "' of "+varName+"(...) cannot be found and is needed. Try to define it.\n",   paramTypeList)
                    exit(1)
                rhsTypeSpec = paramTypeList[0]
                rhsType     = progSpec.fieldTypeKeyword(rhsTypeSpec)
                # TODO: Remove the 'True' and make this check object heirarchies or similar solution
                if True or not isinstance(rhsType, str) and convertedType==rhsType[0]:
                    [leftMod, rightMod] = determinePtrConfigForNewVars(lhsTypeSpec, rhsTypeSpec, useCtor)
                    if(not useCtor): assignValue += " = "    # Use a copy constructor
                    if(isAllocated):
                        assignValue += getCodeAllocStr(innerType, owner)
                    assignValue += "(" + leftMod + CPL[1:-1] + rightMod + ")"
            if(assignValue==''):
                if(owner == 'their' or owner == 'our' or owner == 'my'): assignValue = ' = '+getCodeAllocStr(innerType, owner)+CPL
                else: assignValue = CPL # add "(x, y, z...) to make this into a constructor call.
        elif(progSpec.typeIsPointer(lhsTypeSpec)):
            if(isAllocated):
                assignValue = " = " + getCodeAllocSetStr(innerType, owner, "")
            else:
                assignValue = '= NULL'
        elif(progSpec.isAContainer(lhsTypeSpec)):
            pass
        else:
            fieldTypeCat= progSpec.fieldsTypeCategory(lhsTypeSpec)
            if(fieldTypeCat=='int' or fieldTypeCat=='char' or fieldTypeCat=='double' or fieldTypeCat=='float'):
                assignValue = ' = 0'
            elif(fieldTypeCat=='bool'):
                assignValue = '= false'

    varDeclareStr= convertedType + " " + varName + assignValue
    return(varDeclareStr)

def codeIncrement(varName):
    return "++" + varName

def codeDecrement(varName):
    return "--" + varName

def codeVarFieldRHS_Str(fieldName, convertedType, fieldType, typeSpec, paramList, objsRefed, isAllocated, typeArgList, genericArgs, xlator):
    fieldValueText=""
    fieldOwner=progSpec.getTypeSpecOwner(typeSpec)
    #TODO: make test case
    if paramList!=None:
        if paramList[-1] == "^&useCtor//8":
            del paramList[-1]
        [CPL, paramTypeList] = codeParameterList(fieldName, paramList, None, objsRefed, genericArgs, xlator)
        fieldValueText += CPL
    if isAllocated == True:
        fieldValueText = " = " + getCodeAllocSetStr(fieldType, fieldOwner, "")
    return fieldValueText

def codeConstField_Str(convertedType, fieldName, fieldValueText, className, indent, xlator ):
    if className=='GLOBAL':
        defn = indent + convertedType + ' ' + fieldName + fieldValueText +';\n';
        decl = ''
    else:
        defn = indent + convertedType + ' ' + fieldName +';\n'
        decl = convertedType[7:] + ' ' + progSpec.flattenObjectName(className) + "::"+ fieldName + fieldValueText +';\n\n'
    return [defn, decl]

def codeVarField_Str(convertedType, typeSpec, fieldName, fieldValueText, className, tags, typeArgList, indent):
    #TODO: make test case
    fieldOwner=progSpec.getTypeSpecOwner(typeSpec)
    if fieldOwner=='we':
        defn = indent + convertedType + ' ' + fieldName +';\n'
        decl = convertedType[7:] + ' ' + progSpec.flattenObjectName(className) + "::"+ fieldName + fieldValueText +';\n\n'
    else:
        defn = indent + convertedType + ' ' + fieldName + fieldValueText +';\n'
        decl = ''
    return [defn, decl]

def codeConstructor(className, ctorArgs, callSuper, ctorInit, funcBody):
    if callSuper != '':
        callSuper = ':' + callSuper
        if ctorInit != '':
            callSuper = callSuper + ', '
    elif ctorInit != '':
        ctorInit = ':' + ctorInit
    S = "    " + className + "(" + ctorArgs + ")" + callSuper + ctorInit +"{\n" + funcBody + "    };\n"
    return (S)

def codeConstructors(className, ctorArgs, ctorOvrRide, ctorInit, copyCtorArgs, funcBody, callSuper, xlator):
    S = ''
    if ctorArgs != '':
        S += codeConstructor(className, ctorArgs, callSuper, ctorInit, funcBody)
  #  S += codeConstructor(className, '', callSuper, '', funcBody)
    return S

def codeConstructorInit(fieldName, count, defaultVal, xlator):
    if (count > 0):
        return "," + fieldName+"("+" _"+fieldName+")"
    elif(count == 0):
        return fieldName+"("+" _"+fieldName+")"
    else:
        cdErr("Error in codeConstructorInit.")

def codeConstructorArgText(argFieldName, count, argType, defaultVal, xlator):
    if defaultVal == "NULL":
        defaultVal = "0"
    if defaultVal != '':
        defaultVal = "=" + defaultVal
    return argType + "  _" +argFieldName + defaultVal

def codeCopyConstructor(fieldName, convertedType, isTemplateVar, xlator):
    return ""

def codeConstructorCall(className):
    return '        INIT();\n'

def codeSuperConstructorCall(parentClassName):
    return parentClassName+'()'

def specialFunction(fieldName, xlator):
    if fieldName == "__plus": newFieldName = "operator+"
    elif fieldName == "__minus": newFieldName = "operator-"
    elif fieldName == "__times": newFieldName = "operator*"
    elif fieldName == "__divide": newFieldName = "operator/"
    elif fieldName == "__negate": newFieldName = "operator-"
    elif fieldName == "__plusEqual": newFieldName = "operator+="
    elif fieldName == "__lessThan": newFieldName = "operator<"
    elif fieldName == "__lessOrEq": newFieldName = "operator<="
    elif fieldName == "__greaterThan": newFieldName = "operator>"
    elif fieldName == "__greaterOrEq": newFieldName = "operator>="
    elif fieldName == "__isEqual": newFieldName = "operator=="
    elif fieldName == "__notEqual": newFieldName = "operator!="
    elif fieldName == "__inc": newFieldName = "operator++"
    elif fieldName == "__opAssign": newFieldName = "operator="
    elif fieldName == "__derefPtr": newFieldName = "operator*"
    elif fieldName == "__index": newFieldName = "operator[]"
    else:  newFieldName = fieldName
    return newFieldName

def codeFuncHeaderStr(className, fieldName, typeDefName, argListText, localArgsAllocated, inheritMode, overRideOper, isConstructor, typeArgList, typeSpec, indent):
    structCode=''; funcDefCode=''; globalFuncs='';
    if(className=='GLOBAL'):
        if fieldName=='main':
            funcDefCode += 'int main(int argc, char *argv[])'
            localArgsAllocated.append(['argc', {'owner':'me', 'fieldType':'int', 'arraySpec':None, 'argList':None}])
            localArgsAllocated.append(['argv', {'owner':'their', 'fieldType':'char', 'arraySpec':None,'argList':None}])  # TODO: Wrong. argv should be an array.
        else:
            globalFuncs += typeDefName +' ' + fieldName +"("+argListText+")"
    else:
        typeArgList = progSpec.getTypeArgList(className)
        if(typeArgList != None):
            templateHeader = codeTemplateHeader(className, typeArgList) +"\n"
            className = className + codeTypeArgs(typeArgList)
        else:
            templateHeader = ""
        if overRideOper:
            if fieldName == "operator[]":
                typeDefName += "&"
        if inheritMode=='normal' or inheritMode=='override':
            structCode += indent + typeDefName +' ' + fieldName +"("+argListText+");\n";
            objPrefix = progSpec.flattenObjectName(className) +'::'
            funcDefCode += templateHeader + typeDefName +' ' + objPrefix + fieldName +"("+argListText+")"
        elif inheritMode=='virtual':
            structCode += indent + 'virtual '+typeDefName +' ' + fieldName +"("+argListText +");\n";
            objPrefix = progSpec.flattenObjectName(className) +'::'
            funcDefCode += templateHeader + typeDefName +' ' + objPrefix + fieldName +"("+argListText+")"
        elif inheritMode=='pure-virtual':
            structCode +=  indent + 'virtual ' + typeDefName +' ' + fieldName +"("+argListText +") = 0;\n";
        else: cdErr("Invalid inherit mode found: "+inheritMode)
        if funcDefCode[:7]=="static ": funcDefCode=funcDefCode[7:]
    return [structCode, funcDefCode, globalFuncs]

def getVirtualFuncText(field):
    return ""

def codeTypeArgs(typeArgList):
    typeArgsCode = "<"
    count = 0
    for typeArg in typeArgList:
        if(count>0):typeArgsCode+=", "
        typeArgsCode+=typeArg
        count+=1
    typeArgsCode+=">"
    return(typeArgsCode)

def codeTemplateHeader(structName, typeArgList):
    templateHeader = "\ntemplate<"
    count = 0
    for typeArg in typeArgList:
        if(count>0):templateHeader+=","
        templateHeader+="typename "+typeArg
        count+=1
    templateHeader+=">"
    return(templateHeader)

def extraCodeForTopOfFuntion(argList):
    return ''

def codeSetBits(LHS_Left, LHS_FieldType, prefix, bitMask, RHS, rhsType):
    if (LHS_FieldType =='flag' ):
        return "SetBits("+LHS_Left+"flags, "+prefix+bitMask+", ("+ RHS +")?"+prefix+bitMask+":0" + ");\n"
    elif (LHS_FieldType =='mode' ):
        return "SetBits("+LHS_Left+"flags, "+prefix+bitMask+"Mask, "+ RHS+"<<" +prefix+bitMask+"Offset"+");\n"

def codeSwitchBreak(caseAction, indent, xlator):
    return indent+"    break;\n"

def applyTypecast(typeInCodeDog, itemToAlterType):
    platformType = adjustBaseTypes(typeInCodeDog)
    return '('+platformType+')'+itemToAlterType;

#######################################################

def includeDirective(libHdr):
    if libHdr[0] == '"' or libHdr[0] == "'":
        S = '#include "'+libHdr[1:-1]+'"\n'
    else:
        S = '#include <'+libHdr+'>\n'
    return S

def generateMainFunctionality(classes, tags):
    # TODO: Some deInitialize items should automatically run during abort().
    # TODO: System initCode should happen first in initialize, last in deinitialize.

    runCode = progSpec.fetchTagValue(tags, 'runCode')
    mainFuncCode="""
    me int32: main(me int32: argc, their char: argv ) <- {
        initialize(joinCmdStrings(argc, argv))
        """ + runCode + """
        deinitialize()
        endFunc()
    }

"""
    progSpec.addObject(classes[0], classes[1], 'GLOBAL', 'struct', 'SEQ')
    codeDogParser.AddToObjectFromText(classes[0], classes[1], progSpec.wrapFieldListInObjectDef('GLOBAL',  mainFuncCode ), "C++ main()")

def fetchXlators():
    xlators = {}

    xlators['LanguageName']          = "C++"
    xlators['BuildStrPrefix']        = "g++ -g -std=gnu++17  "
    xlators['fileExtension']         = ".cpp"
    xlators['typeForCounterInt']     = "int64_t"
    xlators['GlobalVarPrefix']       = ""
    xlators['PtrConnector']          = "->"                      # Name segment connector for pointers.
    xlators['ObjConnector']          = "::"                      # Name segment connector for classes.
    xlators['NameSegConnector']      = "."
    xlators['NameSegFuncConnector']  = "."
    xlators['doesLangHaveGlobals']   = "True"
    xlators['funcBodyIndent']        = ""
    xlators['funcsDefInClass']       = "False"
    xlators['MakeConstructors']      = "True"
    xlators['blockPrefix']           = ""
    xlators['usePrefixOnStatics']    = "False"
    xlators['iteratorsUseOperators'] = "True"
    xlators['renderGenerics']        = "False"
    xlators['renameInitFuncs']       = "False"
    xlators['codeFactor']                   = codeFactor
    xlators['codeComparisonStr']            = codeComparisonStr
    xlators['codeIdentityCheck']            = codeIdentityCheck
    xlators['derefPtr']                     = derefPtr
    xlators['checkForTypeCastNeed']         = checkForTypeCastNeed
    xlators['checkForTypeCastNeed']         = checkForTypeCastNeed
    xlators['applyOwner']                   = applyOwner
    xlators['adjustConditional']            = adjustConditional
    xlators['includeDirective']             = includeDirective
    xlators['codeMain']                     = codeMain
    xlators['produceTypeDefs']              = produceTypeDefs
    xlators['addSpecialCode']               = addSpecialCode
    xlators['applyTypecast']                = applyTypecast
    xlators['codeIteratorOperation']        = codeIteratorOperation
    xlators['xlateLangType']                = xlateLangType
    xlators['getContainerType']             = getContainerType
    xlators['recodeStringFunctions']        = recodeStringFunctions
    xlators['langStringFormatterCommand']   = langStringFormatterCommand
    xlators['LanguageSpecificDecorations']  = LanguageSpecificDecorations
    xlators['getCodeAllocStr']              = getCodeAllocStr
    xlators['getCodeAllocSetStr']           = getCodeAllocSetStr
    xlators['codeSpecialReference']         = codeSpecialReference
    xlators['checkIfSpecialAssignmentFormIsNeeded'] = checkIfSpecialAssignmentFormIsNeeded
    xlators['getConstIntFieldStr']          = getConstIntFieldStr
    xlators['codeStructText']               = codeStructText
    xlators['getContainerTypeInfo']         = getContainerTypeInfo
    xlators['codeNewVarStr']                = codeNewVarStr
    xlators['chooseVirtualRValOwner']       = chooseVirtualRValOwner
    xlators['determinePtrConfigForAssignments'] = determinePtrConfigForAssignments
    xlators['iterateRangeContainerStr']     = iterateRangeContainerStr
    xlators['iterateContainerStr']          = iterateContainerStr
    xlators['getEnumStr']                   = getEnumStr
    xlators['getEnumStringifyFunc']         = getEnumStringifyFunc
    xlators['codeVarFieldRHS_Str']          = codeVarFieldRHS_Str
    xlators['codeVarField_Str']             = codeVarField_Str
    xlators['codeFuncHeaderStr']            = codeFuncHeaderStr
    xlators['extraCodeForTopOfFuntion']     = extraCodeForTopOfFuntion
    xlators['codeArrayIndex']               = codeArrayIndex
    xlators['codeSetBits']                  = codeSetBits
    xlators['generateMainFunctionality']    = generateMainFunctionality
    xlators['addGLOBALSpecialCode']         = addGLOBALSpecialCode
    xlators['codeArgText']                  = codeArgText
    xlators['codeConstructor']              = codeConstructor
    xlators['codeConstructors']             = codeConstructors
    xlators['codeConstructorInit']          = codeConstructorInit
    xlators['codeIncrement']                = codeIncrement
    xlators['codeDecrement']                = codeDecrement
    xlators['codeConstructorArgText']       = codeConstructorArgText
    xlators['codeSwitchBreak']              = codeSwitchBreak
    xlators['codeCopyConstructor']          = codeCopyConstructor
    xlators['codeRangeSpec']                = codeRangeSpec
    xlators['codeConstField_Str']           = codeConstField_Str
    xlators['checkForTypeCastNeed']         = checkForTypeCastNeed
    xlators['codeConstructorCall']          = codeConstructorCall
    xlators['codeSuperConstructorCall']     = codeSuperConstructorCall
    xlators['getVirtualFuncText']           = getVirtualFuncText
    xlators['specialFunction']              = specialFunction
    xlators['getUnwrappedClassOwner']       = getUnwrappedClassOwner
    xlators['xlateLangType']                = xlateLangType
    xlators['makePtrOpt']                   = makePtrOpt
    xlators['adjustBaseTypes']              = adjustBaseTypes
    return(xlators)
