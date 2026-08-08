#include "types.h"

#ifdef STAGE3E2_HEADER_TEST
#include "constants/generated/project_map_headers.h"

#define RETAIL_MAP_HEADER_BASE ((const u8 *)0x020F6BE0)
#define MAP_HEADER_BYTES 24u

volatile u32 gStage3E2LastHeaderLookup;
volatile u32 gStage3E2ProjectHeaderLookups;
volatile u32 gStage3E2InvalidHeaderLookups;

static const u8 *ProjectMapHeader_Get(u32 mapId)
{
    gStage3E2LastHeaderLookup = mapId;
    if (mapId < PROJECT_MAP_HEADER_BASE)
        return RETAIL_MAP_HEADER_BASE + mapId * MAP_HEADER_BYTES;
    if (mapId - PROJECT_MAP_HEADER_BASE < PROJECT_MAP_HEADER_COUNT) {
        gStage3E2ProjectHeaderLookups++;
        return gProjectMapHeaders[mapId - PROJECT_MAP_HEADER_BASE];
    }
    gStage3E2InvalidHeaderLookups++;
    return RETAIL_MAP_HEADER_BASE;
}

static u16 ReadLE16(const u8 *data, u32 offset)
{
    return (u16)(data[offset] | data[offset + 1] << 8);
}

static u32 ReadLE32(const u8 *data, u32 offset)
{
    return (u32)data[offset] | (u32)data[offset + 1] << 8 |
           (u32)data[offset + 2] << 16 | (u32)data[offset + 3] << 24;
}

u32 ExpandedMapHeader_GetAreaDataBank(u32 id) { return ProjectMapHeader_Get(id)[1]; }
u32 ExpandedMapHeader_GetMoveModelBank(u32 id) { return ReadLE16(ProjectMapHeader_Get(id), 2) & 0xF; }
u32 ExpandedMapHeader_GetMatrixId(u32 id) { return ReadLE16(ProjectMapHeader_Get(id), 4); }
u32 ExpandedMapHeader_GetMsgBank(u32 id) { return ReadLE16(ProjectMapHeader_Get(id), 10); }
u32 ExpandedMapHeader_GetScriptsBank(u32 id) { return ReadLE16(ProjectMapHeader_Get(id), 6); }
u32 ExpandedMapHeader_GetScriptHeaderBank(u32 id) { return ReadLE16(ProjectMapHeader_Get(id), 8); }
u32 ExpandedMapHeader_GetDayMusicId(u32 id) { return ReadLE16(ProjectMapHeader_Get(id), 12); }
u32 ExpandedMapHeader_GetNightMusicId(u32 id) { return ReadLE16(ProjectMapHeader_Get(id), 14); }
u32 ExpandedMapHeader_HasWildEncounters(u32 id) { return ProjectMapHeader_Get(id)[0] != 0xFF; }
u32 ExpandedMapHeader_GetWildEncounterBank(u32 id) { return ProjectMapHeader_Get(id)[0]; }
u32 ExpandedMapHeader_GetEventsBank(u32 id) { return ReadLE16(ProjectMapHeader_Get(id), 16); }
u32 ExpandedMapHeader_GetMapSec(u32 id) { return ProjectMapHeader_Get(id)[18]; }
u32 ExpandedMapHeader_GetAreaIcon(u32 id) { return ProjectMapHeader_Get(id)[19] & 0xF; }
u32 ExpandedMapHeader_GetMomCallIntroParam(u32 id) { return ProjectMapHeader_Get(id)[19] >> 4; }
u32 ExpandedMapHeader_GetRegionNo(u32 id) { return ReadLE32(ProjectMapHeader_Get(id), 20) & 1; }
u32 ExpandedMapHeader_GetWeatherType(u32 id) { return ReadLE32(ProjectMapHeader_Get(id), 20) >> 1 & 0x7F; }
u32 ExpandedMapHeader_GetCameraType(u32 id) { return ReadLE32(ProjectMapHeader_Get(id), 20) >> 12 & 0x3F; }
u32 ExpandedMapHeader_GetBattleBg(u32 id) { return ReadLE32(ProjectMapHeader_Get(id), 20) >> 20 & 0x1F; }
u32 ExpandedMapHeader_IsEscapeRopeAllowed(u32 id) { return ReadLE32(ProjectMapHeader_Get(id), 20) >> 27 & 1; }
u32 ExpandedMapHeader_IsFlyAllowed(u32 id) { return ReadLE32(ProjectMapHeader_Get(id), 20) >> 28 & 1; }
u32 ExpandedMapHeader_IsBikeAllowed(u32 id) { return ReadLE32(ProjectMapHeader_Get(id), 20) >> 25 & 1; }
u32 ExpandedMapHeader_CanPlacePhoneCalls(u32 id) { return ReadLE32(ProjectMapHeader_Get(id), 20) >> 29 & 1; }
u32 ExpandedMapHeader_CanReceivePhoneCalls(u32 id) { return ReadLE32(ProjectMapHeader_Get(id), 20) >> 30 & 1; }
u32 ExpandedMapHeader_CanReceiveRadioSignal(u32 id) { return ReadLE32(ProjectMapHeader_Get(id), 20) >> 31; }
u32 ExpandedMapHeader_GetMapType(u32 id) { return ReadLE32(ProjectMapHeader_Get(id), 20) >> 8 & 0xF; }
u32 ExpandedMapHeader_GetFollowMode(u32 id) { return ReadLE32(ProjectMapHeader_Get(id), 20) >> 18 & 3; }

void ExpandedMapHeader_GetWorldMapCoords(u32 id, s16 *x, s16 *y)
{
    u16 packed = ReadLE16(ProjectMapHeader_Get(id), 2);
    *x = (packed >> 4) & 0x3F;
    *y = (packed >> 10) & 0x3F;
}
#endif
